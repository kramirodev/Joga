"""Orquestração da verificação de CNPJ da organização (ADR 0062).

O fluxo é automático e falha fechado: sem consulta confiável não há aprovação.
O CPF do responsável só existe em claro na memória da requisição; a comparação
com o QSA usa a máscara devolvida pela Receita e o perfil guarda o CPF cifrado.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.modules.identity.audit import record_audit
from app.modules.identity.clock import utcnow
from app.modules.organizations.cnpj import (
    SITUACAO_ATIVA,
    CnpjLookup,
    CnpjNotFound,
    CnpjProviderUnavailable,
    CnpjRecord,
    InvalidCnpj,
    address_matches,
    cpf_masked_matches,
    mask_cnpj,
    names_match,
    normalize_cnpj,
)
from app.modules.organizations.models import (
    Organization,
    OrganizationMembership,
    OrganizationVenue,
)
from app.modules.organizations.permissions import Role
from app.modules.profile.cpf import (
    CpfDecryptionError,
    CpfKeyUnavailable,
    InvalidCpf,
    decrypt_cpf,
    encrypt_cpf,
    hash_cpf,
    normalize_cpf,
)
from app.modules.profile.cpf import (
    mask_cpf as mask_profile_cpf,
)
from app.modules.profile.models import UserProfile

VERIFICATION_PENDING = "pending"
VERIFICATION_VERIFIED = "verified"
VERIFICATION_INVALID = "invalid"


class CnpjVerificationError(Exception):
    """Falha de verificação com código estável para o painel."""

    code = "cnpj_invalid"
    http_status = 422

    def __init__(self, reason: str, *, details: dict[str, Any] | None = None) -> None:
        super().__init__(reason)
        self.reason = reason
        self.details: dict[str, Any] = {"reason": reason}
        if details:
            self.details.update(details)


class CnpjInvalid(CnpjVerificationError):
    code = "cnpj_invalid"


class CnpjInactive(CnpjVerificationError):
    code = "cnpj_inactive"


class CnpjCnaeIncompatible(CnpjVerificationError):
    code = "cnpj_cnae_incompatible"


class CnpjAddressMismatch(CnpjVerificationError):
    code = "cnpj_address_mismatch"


class CnpjOwnerMismatch(CnpjVerificationError):
    code = "cnpj_owner_mismatch"


class CnpjLookupUnavailable(CnpjVerificationError):
    code = "cnpj_lookup_unavailable"


class CpfInvalid(CnpjVerificationError):
    code = "cpf_invalid"


class CpfVerificationUnavailable(CnpjVerificationError):
    code = "cpf_unavailable"
    http_status = 503


class CpfAlreadyRegistered(CnpjVerificationError):
    """O CPF pertence a outra conta (ADR 0065); a organização não é criada."""

    code = "cpf_already_registered"
    http_status = 409


@dataclass(frozen=True)
class CnpjVerification:
    """Resultado aprovado de uma consulta, pronto para persistir."""

    cnpj: str
    status: str
    snapshot: dict[str, Any]
    matched_cnae: str
    owner_cpf_masked: str | None

    def audit_details(self) -> dict[str, Any]:
        return {
            "result": VERIFICATION_VERIFIED,
            "reason": "active",
            "cnpj_masked": mask_cnpj(self.cnpj),
            "situacao_cadastral": self.status,
            "cnae_matched": self.matched_cnae,
            "owner_cpf_masked": self.owner_cpf_masked,
        }


@dataclass(frozen=True)
class RecheckReport:
    """Resumo de uma execução do worker de reverificação."""

    checked: int = 0
    verified: int = 0
    invalid: int = 0
    unavailable: int = 0


def verify_new_organization(
    session: Session,
    *,
    actor_user_id: uuid.UUID,
    cnpj: str,
    cpf: str,
    settings: Settings,
    lookup: CnpjLookup,
) -> CnpjVerification:
    """Valida CNPJ, situação, CNAE, endereço e responsável no QSA.

    O endereço só é confrontado na criação da quadra, quando existe. Aqui a
    aprovação exige situação ATIVA, CNAE esportivo e CPF/nome do responsável no
    QSA. Qualquer falha externa interrompe a criação da organização.
    """

    try:
        cpf_digits = normalize_cpf(cpf)
    except InvalidCpf as error:
        raise CpfInvalid("invalid_cpf", details={"cpf_present": False}) from error

    profile = session.get(UserProfile, actor_user_id)
    if profile is not None and profile.cpf_ciphertext is not None:
        try:
            stored_cpf = decrypt_cpf(
                profile.cpf_ciphertext,
                actor_user_id,
                profile.cpf_key_id,
                settings,
            )
        except (CpfKeyUnavailable, CpfDecryptionError) as error:
            raise CpfVerificationUnavailable("cpf_unavailable") from error
        if stored_cpf != cpf_digits:
            raise CnpjOwnerMismatch(
                "cpf_profile_mismatch",
                details={"owner_cpf_masked": mask_profile_cpf(profile.cpf_last2)},
            )

    try:
        normalized_cnpj = normalize_cnpj(cnpj)
    except InvalidCnpj as error:
        raise CnpjInvalid("invalid_digits") from error

    try:
        record = lookup.lookup(normalized_cnpj)
    except CnpjNotFound as error:
        raise CnpjInvalid(
            "not_found",
            details={"cnpj_masked": mask_cnpj(normalized_cnpj)},
        ) from error
    except CnpjProviderUnavailable as error:
        raise CnpjLookupUnavailable(
            "provider_unavailable",
            details={"cnpj_masked": mask_cnpj(normalized_cnpj)},
        ) from error

    matched_cnae = _validate_record(record)
    owner_masked = _validate_owner(record, profile=profile, cpf=cpf_digits)

    # Só grava o CPF depois de o QSA confirmar que ele pertence ao responsável.
    _persist_cpf_if_absent(
        session,
        profile=profile,
        actor_user_id=actor_user_id,
        cpf=cpf_digits,
        settings=settings,
    )

    return CnpjVerification(
        cnpj=record.cnpj,
        status=record.situacao_cadastral,
        snapshot=record.snapshot(),
        matched_cnae=matched_cnae,
        owner_cpf_masked=owner_masked,
    )


def validate_venue_address(
    organization: Organization,
    *,
    city: str | None,
    state: str | None,
    postal_code: str | None,
) -> None:
    """Exige que a quadra fique no município/CEP do CNPJ aprovado."""

    if organization.is_platform:
        return
    if organization.cnpj_snapshot is None:
        raise CnpjAddressMismatch("cnpj_not_verified")
    if not address_matches(
        organization.cnpj_snapshot,
        city=city,
        state=state,
        postal_code=postal_code,
    ):
        snapshot = organization.cnpj_snapshot
        raise CnpjAddressMismatch(
            "address_mismatch",
            details={
                "cnpj_masked": (
                    mask_cnpj(organization.cnpj) if organization.cnpj is not None else None
                ),
                "cnpj_municipio": snapshot.get("municipio"),
                "cnpj_uf": snapshot.get("uf"),
                "cnpj_cep": snapshot.get("cep"),
            },
        )


class OrganizationVerificationService:
    """Reverificação periódica e despublicação de organizações inválidas."""

    def __init__(self, session: Session, settings: Settings, lookup: CnpjLookup) -> None:
        self.session = session
        self.settings = settings
        self.lookup = lookup

    def recheck_due(self, *, limit: int = 20) -> RecheckReport:
        """Processa organizações vencidas em lote pequeno e staggered.

        A seleção usa ``cnpj_next_check_at``, que nasce em ``created_at + 7
        dias`` e avança a partir de ``now`` a cada execução. Assim cada
        organização tem seu próprio relógio e não existe varredura global.
        """

        if limit < 1:
            raise ValueError("limit deve ser positivo")
        now = utcnow()
        due = list(
            self.session.scalars(
                select(Organization)
                .where(
                    Organization.cnpj.is_not(None),
                    Organization.cnpj_next_check_at.is_not(None),
                    Organization.cnpj_next_check_at <= now,
                    Organization.is_platform.is_(False),
                )
                .order_by(Organization.cnpj_next_check_at, Organization.id)
                .limit(limit)
            ).all()
        )
        checked = verified = invalid = unavailable = 0
        for organization in due:
            checked += 1
            outcome = self._recheck(organization, now=now)
            if outcome == VERIFICATION_VERIFIED:
                verified += 1
            elif outcome == VERIFICATION_INVALID:
                invalid += 1
            else:
                unavailable += 1
        return RecheckReport(
            checked=checked,
            verified=verified,
            invalid=invalid,
            unavailable=unavailable,
        )

    def _recheck(self, organization: Organization, *, now: datetime) -> str:
        assert organization.cnpj is not None
        try:
            record = self.lookup.lookup(organization.cnpj)
        except (CnpjNotFound, CnpjProviderUnavailable, InvalidCnpj) as error:
            organization.cnpj_next_check_at = now + timedelta(
                hours=self.settings.organization_cnpj_retry_hours
            )
            record_audit(
                self.session,
                actor_user_id=None,
                organization_id=organization.id,
                action="organization.cnpj_recheck_unavailable",
                resource_type="organization",
                resource_id=organization.id,
                details={
                    "result": VERIFICATION_PENDING,
                    "reason": type(error).__name__,
                    "cnpj_masked": mask_cnpj(organization.cnpj),
                },
            )
            self.session.flush()
            return VERIFICATION_PENDING

        reason = "active"
        matched_cnae = record.compatible_cnae()
        try:
            _validate_record(record)
            if not self._owner_still_matches(organization, record):
                raise CnpjOwnerMismatch("owner_mismatch")
            if not self._venues_still_match(organization, record):
                raise CnpjAddressMismatch("address_mismatch")
        except CnpjVerificationError as error:
            organization.cnpj_status = record.situacao_cadastral
            organization.cnpj_snapshot = record.snapshot()
            organization.verification_status = VERIFICATION_INVALID
            organization.cnpj_next_check_at = now + timedelta(
                days=self.settings.organization_cnpj_recheck_days
            )
            unpublished = self._unpublish_venues(organization.id)
            record_audit(
                self.session,
                actor_user_id=None,
                organization_id=organization.id,
                action="organization.cnpj_recheck_failed",
                resource_type="organization",
                resource_id=organization.id,
                details={
                    "result": VERIFICATION_INVALID,
                    "reason": error.reason,
                    "cnpj_masked": mask_cnpj(organization.cnpj),
                    "situacao_cadastral": record.situacao_cadastral,
                    "cnae_matched": matched_cnae,
                    "venues_unpublished": unpublished,
                },
            )
            self.session.flush()
            return VERIFICATION_INVALID

        organization.cnpj_status = record.situacao_cadastral
        organization.cnpj_snapshot = record.snapshot()
        organization.verification_status = VERIFICATION_VERIFIED
        organization.cnpj_verified_at = now
        organization.cnpj_next_check_at = now + timedelta(
            days=self.settings.organization_cnpj_recheck_days
        )
        record_audit(
            self.session,
            actor_user_id=None,
            organization_id=organization.id,
            action="organization.cnpj_recheck_ok",
            resource_type="organization",
            resource_id=organization.id,
            details={
                "result": VERIFICATION_VERIFIED,
                "reason": reason,
                "cnpj_masked": mask_cnpj(organization.cnpj),
                "situacao_cadastral": record.situacao_cadastral,
                "cnae_matched": matched_cnae,
            },
        )
        self.session.flush()
        return VERIFICATION_VERIFIED

    def _owner_still_matches(self, organization: Organization, record: CnpjRecord) -> bool:
        """Reconfere o responsável quando o CPF cifrado está disponível.

        Se a chave estiver indisponível, a reverificação mantém a organização
        aprovada e tenta de novo no próximo ciclo; indisponibilidade interna não
        pode despublicar toda a base. Com múltiplos proprietários, basta um CPF
        legível e presente no QSA para manter o vínculo.
        """

        owners = self.session.scalars(
            select(OrganizationMembership)
            .where(
                OrganizationMembership.organization_id == organization.id,
                OrganizationMembership.role == Role.OWNER.value,
            )
            .order_by(OrganizationMembership.created_at)
        ).all()
        if not owners:
            return False
        checked_any = False
        for owner in owners:
            profile = self.session.get(UserProfile, owner.user_id)
            if profile is None or profile.cpf_ciphertext is None:
                continue
            try:
                cpf = decrypt_cpf(
                    profile.cpf_ciphertext,
                    owner.user_id,
                    profile.cpf_key_id,
                    self.settings,
                )
            except (CpfKeyUnavailable, CpfDecryptionError):
                continue
            checked_any = True
            if any(
                cpf_masked_matches(partner.cpf_masked, cpf)
                and names_match(profile.display_name, partner.nome)
                for partner in record.qsa
            ):
                return True
        # Nenhum CPF pôde ser lido: mantém o status e tenta no próximo ciclo.
        return not checked_any

    def _venues_still_match(self, organization: Organization, record: CnpjRecord) -> bool:
        snapshot = record.snapshot()
        venues = self.session.scalars(
            select(OrganizationVenue).where(OrganizationVenue.organization_id == organization.id)
        ).all()
        for venue in venues:
            if venue.status != "active":
                continue
            if not address_matches(
                snapshot,
                city=venue.city,
                state=venue.state,
                postal_code=venue.postal_code,
            ):
                return False
        return True

    def _unpublish_venues(self, organization_id: uuid.UUID) -> int:
        venues = self.session.scalars(
            select(OrganizationVenue).where(OrganizationVenue.organization_id == organization_id)
        ).all()
        changed = 0
        for venue in venues:
            if venue.status == "inactive" and not venue.is_public:
                continue
            venue.status = "inactive"
            venue.is_public = False
            changed += 1
        return changed


def _validate_record(record: CnpjRecord) -> str:
    if record.situacao_cadastral != SITUACAO_ATIVA:
        raise CnpjInactive(
            "inactive",
            details={
                "cnpj_masked": mask_cnpj(record.cnpj),
                "situacao_cadastral": record.situacao_cadastral,
            },
        )
    matched_cnae = record.compatible_cnae()
    if matched_cnae is None:
        raise CnpjCnaeIncompatible(
            "cnae_incompatible",
            details={
                "cnpj_masked": mask_cnpj(record.cnpj),
                "cnae_fiscal": record.cnae_fiscal,
            },
        )
    return matched_cnae


def _validate_owner(
    record: CnpjRecord,
    *,
    profile: UserProfile | None,
    cpf: str,
) -> str | None:
    display_name = profile.display_name if profile is not None else None
    if not display_name:
        raise CnpjOwnerMismatch("responsible_name_missing")
    cpf_matches = [partner for partner in record.qsa if cpf_masked_matches(partner.cpf_masked, cpf)]
    if not cpf_matches:
        raise CnpjOwnerMismatch(
            "cpf_not_in_qsa",
            details={"cnpj_masked": mask_cnpj(record.cnpj)},
        )
    if not any(names_match(display_name, partner.nome) for partner in cpf_matches):
        raise CnpjOwnerMismatch(
            "name_not_in_qsa",
            details={"cnpj_masked": mask_cnpj(record.cnpj)},
        )
    # A máscara do CPF do sócio já vem da Receita; nunca guardamos o CPF claro.
    return cpf_matches[0].cpf_masked


def _persist_cpf_if_absent(
    session: Session,
    *,
    profile: UserProfile | None,
    actor_user_id: uuid.UUID,
    cpf: str,
    settings: Settings,
) -> None:
    if profile is not None and profile.cpf_ciphertext is not None:
        return
    cpf_hash = hash_cpf(cpf, settings)
    other = session.scalar(
        select(UserProfile.user_id).where(
            UserProfile.cpf_hash == cpf_hash,
            UserProfile.user_id != actor_user_id,
        )
    )
    if other is not None:
        raise CpfAlreadyRegistered("cpf_already_registered")
    try:
        ciphertext, key_id, last2 = encrypt_cpf(cpf, actor_user_id, settings)
    except CpfKeyUnavailable as error:
        raise CpfVerificationUnavailable("cpf_unavailable") from error
    if profile is None:
        profile = UserProfile(user_id=actor_user_id)
        session.add(profile)
    profile.cpf_ciphertext = ciphertext
    profile.cpf_key_id = key_id
    profile.cpf_last2 = last2
    profile.cpf_hash = cpf_hash
    profile.cpf_updated_at = utcnow()
    record_audit(
        session,
        actor_user_id=actor_user_id,
        action="user.cpf_updated",
        resource_type="user",
        resource_id=actor_user_id,
        details={"cpf_present": True},
    )
    try:
        session.flush()
    except IntegrityError as error:
        # Corrida com outra conta: o índice único de ``cpf_hash`` vence.
        raise CpfAlreadyRegistered("cpf_already_registered") from error


__all__ = [
    "CnpjAddressMismatch",
    "CnpjCnaeIncompatible",
    "CnpjInactive",
    "CnpjInvalid",
    "CnpjLookupUnavailable",
    "CnpjOwnerMismatch",
    "CnpjVerification",
    "CnpjVerificationError",
    "CpfInvalid",
    "CpfAlreadyRegistered",
    "CpfVerificationUnavailable",
    "OrganizationVerificationService",
    "RecheckReport",
    "VERIFICATION_INVALID",
    "VERIFICATION_PENDING",
    "VERIFICATION_VERIFIED",
    "validate_venue_address",
    "verify_new_organization",
]
