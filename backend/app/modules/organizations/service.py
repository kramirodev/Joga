"""Casos de uso de organizações, membros, estabelecimentos e auditoria."""

from __future__ import annotations

import uuid
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.modules.identity.audit import record_audit
from app.modules.identity.models import AuditLog, User
from app.modules.organizations.models import (
    Organization,
    OrganizationMembership,
    OrganizationVenue,
)
from app.modules.organizations.permissions import (
    Capability,
    Role,
    capabilities_for,
)
from app.modules.profile.models import UserProfile


class OrganizationError(Exception):
    """Erro base do domínio de organizações."""


class OrganizationNotFound(OrganizationError):
    """Organização inexistente ou fora do escopo do usuário."""


class VenueNotFound(OrganizationError):
    """Estabelecimento inexistente ou fora do escopo do usuário."""


class MemberNotFound(OrganizationError):
    """Vínculo inexistente."""


class UserNotFound(OrganizationError):
    """Usuário alvo inexistente."""


class UserNotActive(OrganizationError):
    """Usuário alvo não está apto a receber vínculo."""


class AlreadyMember(OrganizationError):
    """Usuário já possui vínculo com a organização."""


class Forbidden(OrganizationError):
    """Papel sem a capacidade exigida."""


class CannotManageRole(OrganizationError):
    """Papel do ator não permite gerenciar o papel alvo."""


class LastOwner(OrganizationError):
    """A organização não pode ficar sem proprietário."""


class InvalidInput(OrganizationError):
    """Dados inválidos para a operação."""


@dataclass(frozen=True)
class OrganizationAccess:
    """Organização e o papel do usuário nela."""

    organization: Organization
    role: Role


@dataclass(frozen=True)
class MemberRecord:
    """Vínculo com dados mínimos de apresentação."""

    membership: OrganizationMembership
    user: User
    display_name: str | None


class OrganizationService:
    """Operações multi-tenant com autorização por objeto."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def create(self, actor_user_id: uuid.UUID, name: str) -> Organization:
        """Cria a organização e o vínculo de proprietário na mesma transação."""

        self._require_active_user(actor_user_id)
        organization = Organization(name=_clean_organization_name(name))
        self.session.add(organization)
        self.session.flush()

        self.session.add(
            OrganizationMembership(
                organization_id=organization.id,
                user_id=actor_user_id,
                role=Role.OWNER.value,
            )
        )
        record_audit(
            self.session,
            actor_user_id=actor_user_id,
            organization_id=organization.id,
            action="organization.created",
            resource_type="organization",
            resource_id=organization.id,
            details={"name": organization.name},
        )
        self.session.flush()
        return organization

    def list_for_user(self, actor_user_id: uuid.UUID) -> list[OrganizationAccess]:
        """Lista apenas organizações das quais o usuário é membro."""

        rows = self.session.execute(
            select(Organization, OrganizationMembership.role)
            .join(
                OrganizationMembership,
                OrganizationMembership.organization_id == Organization.id,
            )
            .where(OrganizationMembership.user_id == actor_user_id)
            .order_by(Organization.name, Organization.id)
        ).all()
        return [OrganizationAccess(organization=row[0], role=Role(row[1])) for row in rows]

    def get(self, actor_user_id: uuid.UUID, organization_id: uuid.UUID) -> OrganizationAccess:
        """Retorna a organização somente se o usuário for membro."""

        membership = self._require_membership(actor_user_id, organization_id)
        organization = self.session.get(Organization, organization_id)
        if organization is None:
            raise OrganizationNotFound
        return OrganizationAccess(organization=organization, role=Role(membership.role))

    def update(
        self,
        actor_user_id: uuid.UUID,
        organization_id: uuid.UUID,
        name: str,
    ) -> Organization:
        """Atualiza o nome da organização e registra a alteração."""

        organization = self._lock_organization(organization_id)
        self._require_capability(actor_user_id, organization_id, Capability.ORGANIZATION_UPDATE)
        normalized = _clean_organization_name(name)
        previous = organization.name
        organization.name = normalized
        record_audit(
            self.session,
            actor_user_id=actor_user_id,
            organization_id=organization_id,
            action="organization.updated",
            resource_type="organization",
            resource_id=organization_id,
            details={"name": {"from": previous, "to": normalized}},
        )
        self.session.flush()
        return organization

    def list_members(
        self,
        actor_user_id: uuid.UUID,
        organization_id: uuid.UUID,
    ) -> list[MemberRecord]:
        """Lista membros; operadores podem consultar, mas não alterar."""

        self._require_capability(actor_user_id, organization_id, Capability.MEMBERS_READ)
        rows = self.session.execute(
            select(OrganizationMembership, User, UserProfile.display_name)
            .join(User, User.id == OrganizationMembership.user_id)
            .outerjoin(UserProfile, UserProfile.user_id == User.id)
            .where(OrganizationMembership.organization_id == organization_id)
            .order_by(OrganizationMembership.created_at, OrganizationMembership.user_id)
        ).all()
        return [MemberRecord(membership=row[0], user=row[1], display_name=row[2]) for row in rows]

    def _member_record(
        self,
        organization_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> MemberRecord:
        row = self.session.execute(
            select(OrganizationMembership, User, UserProfile.display_name)
            .join(User, User.id == OrganizationMembership.user_id)
            .outerjoin(UserProfile, UserProfile.user_id == User.id)
            .where(
                OrganizationMembership.organization_id == organization_id,
                OrganizationMembership.user_id == user_id,
            )
        ).one_or_none()
        if row is None:
            raise MemberNotFound
        return MemberRecord(membership=row[0], user=row[1], display_name=row[2])

    def add_member(
        self,
        actor_user_id: uuid.UUID,
        organization_id: uuid.UUID,
        user_id: uuid.UUID,
        role: Role,
    ) -> MemberRecord:
        """Adiciona um membro respeitando a hierarquia de papéis."""

        self._lock_organization(organization_id)
        actor_membership = self._require_capability(
            actor_user_id, organization_id, Capability.MEMBERS_MANAGE
        )
        actor_role = Role(actor_membership.role)
        _ensure_can_assign(actor_role, role)
        self._require_active_user(user_id)

        if self._membership(organization_id, user_id) is not None:
            raise AlreadyMember

        membership = OrganizationMembership(
            organization_id=organization_id,
            user_id=user_id,
            role=role.value,
        )
        try:
            with self.session.begin_nested():
                self.session.add(membership)
                self.session.flush()
        except IntegrityError as exc:
            raise AlreadyMember from exc

        record_audit(
            self.session,
            actor_user_id=actor_user_id,
            organization_id=organization_id,
            action="membership.added",
            resource_type="organization_membership",
            resource_id=membership.id,
            details={"target_user_id": str(user_id), "role": role.value},
        )
        self.session.flush()
        return self._member_record(organization_id, user_id)

    def change_member_role(
        self,
        actor_user_id: uuid.UUID,
        organization_id: uuid.UUID,
        user_id: uuid.UUID,
        role: Role,
    ) -> MemberRecord:
        """Altera o papel de um membro, sem permitir escalada indevida."""

        self._lock_organization(organization_id)
        actor_membership = self._require_capability(
            actor_user_id, organization_id, Capability.MEMBERS_MANAGE
        )
        actor_role = Role(actor_membership.role)
        target = self._membership(organization_id, user_id)
        if target is None:
            raise MemberNotFound

        target_role = Role(target.role)
        if target.user_id != actor_user_id:
            _ensure_can_manage_target(actor_role, target_role)
        _ensure_can_assign(actor_role, role)

        if target_role == Role.OWNER and role != Role.OWNER:
            self._ensure_not_last_owner(organization_id, target)
        if target_role == role:
            return self._member_record(organization_id, user_id)

        target.role = role.value
        record_audit(
            self.session,
            actor_user_id=actor_user_id,
            organization_id=organization_id,
            action="membership.role_changed",
            resource_type="organization_membership",
            resource_id=target.id,
            details={
                "target_user_id": str(user_id),
                "from": target_role.value,
                "to": role.value,
            },
        )
        self.session.flush()
        return self._member_record(organization_id, user_id)

    def remove_member(
        self,
        actor_user_id: uuid.UUID,
        organization_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> None:
        """Remove um vínculo; o último proprietário não pode ser removido."""

        self._lock_organization(organization_id)
        actor_membership = self._require_capability(
            actor_user_id, organization_id, Capability.MEMBERS_MANAGE
        )
        actor_role = Role(actor_membership.role)
        target = self._membership(organization_id, user_id)
        if target is None:
            raise MemberNotFound

        target_role = Role(target.role)
        if target.user_id != actor_user_id:
            _ensure_can_manage_target(actor_role, target_role)
        if target_role == Role.OWNER:
            self._ensure_not_last_owner(organization_id, target)

        membership_id = target.id
        self.session.delete(target)
        record_audit(
            self.session,
            actor_user_id=actor_user_id,
            organization_id=organization_id,
            action="membership.removed",
            resource_type="organization_membership",
            resource_id=membership_id,
            details={"target_user_id": str(user_id), "role": target_role.value},
        )
        self.session.flush()

    def create_venue(
        self,
        actor_user_id: uuid.UUID,
        organization_id: uuid.UUID,
        *,
        name: str,
        city: str | None = None,
        state: str | None = None,
        address_line: str | None = None,
    ) -> OrganizationVenue:
        """Cria um estabelecimento vinculado à organização."""

        self._require_capability(actor_user_id, organization_id, Capability.VENUES_MANAGE)
        venue = OrganizationVenue(
            organization_id=organization_id,
            name=_clean_venue_name(name),
            city=_clean_optional(city, max_length=120),
            state=_clean_state(state),
            address_line=_clean_optional(address_line, max_length=200),
        )
        self.session.add(venue)
        self.session.flush()
        record_audit(
            self.session,
            actor_user_id=actor_user_id,
            organization_id=organization_id,
            action="venue.created",
            resource_type="venue",
            resource_id=venue.id,
            details={"name": venue.name},
        )
        self.session.flush()
        return venue

    def list_venues(
        self,
        actor_user_id: uuid.UUID,
        organization_id: uuid.UUID,
    ) -> Sequence[OrganizationVenue]:
        """Lista estabelecimentos da organização autorizada."""

        self._require_capability(actor_user_id, organization_id, Capability.VENUES_READ)
        return self.session.scalars(
            select(OrganizationVenue)
            .where(OrganizationVenue.organization_id == organization_id)
            .order_by(OrganizationVenue.name, OrganizationVenue.id)
        ).all()

    def get_venue(
        self,
        actor_user_id: uuid.UUID,
        organization_id: uuid.UUID,
        venue_id: uuid.UUID,
    ) -> OrganizationVenue:
        """Busca o estabelecimento sempre no escopo da organização."""

        self._require_capability(actor_user_id, organization_id, Capability.VENUES_READ)
        venue = self.session.scalar(
            select(OrganizationVenue).where(
                OrganizationVenue.id == venue_id,
                OrganizationVenue.organization_id == organization_id,
            )
        )
        if venue is None:
            raise VenueNotFound
        return venue

    def update_venue(
        self,
        actor_user_id: uuid.UUID,
        organization_id: uuid.UUID,
        venue_id: uuid.UUID,
        *,
        changes: Mapping[str, str | None],
    ) -> OrganizationVenue:
        """Atualiza apenas campos permitidos do estabelecimento."""

        self._require_capability(actor_user_id, organization_id, Capability.VENUES_MANAGE)
        venue = self.session.scalar(
            select(OrganizationVenue).where(
                OrganizationVenue.id == venue_id,
                OrganizationVenue.organization_id == organization_id,
            )
        )
        if venue is None:
            raise VenueNotFound

        applied: dict[str, Any] = {}
        for field, value in changes.items():
            if field == "name":
                if value is None:
                    raise InvalidInput
                cleaned: str | None = _clean_venue_name(value)
            elif field in {"city", "address_line"}:
                cleaned = _clean_optional(value, max_length=120 if field == "city" else 200)
            elif field == "state":
                cleaned = _clean_state(value)
            elif field == "status":
                if value not in {"active", "inactive"}:
                    raise InvalidInput
                cleaned = value
            else:
                raise InvalidInput

            previous = getattr(venue, field)
            if previous != cleaned:
                setattr(venue, field, cleaned)
                applied[field] = {"from": previous, "to": cleaned}

        if applied:
            record_audit(
                self.session,
                actor_user_id=actor_user_id,
                organization_id=organization_id,
                action="venue.updated",
                resource_type="venue",
                resource_id=venue.id,
                details={"changes": applied},
            )
            self.session.flush()
        return venue

    def list_audit(
        self,
        actor_user_id: uuid.UUID,
        organization_id: uuid.UUID,
        *,
        limit: int,
        offset: int,
    ) -> Sequence[AuditLog]:
        """Lista a trilha append-only da organização."""

        self._require_capability(actor_user_id, organization_id, Capability.AUDIT_READ)
        return self.session.scalars(
            select(AuditLog)
            .where(AuditLog.organization_id == organization_id)
            .order_by(AuditLog.created_at.desc(), AuditLog.id.desc())
            .limit(limit)
            .offset(offset)
        ).all()

    def _lock_organization(self, organization_id: uuid.UUID) -> Organization:
        """Serializa alterações de vínculo por organização no PostgreSQL."""

        organization = self.session.scalar(
            select(Organization).where(Organization.id == organization_id).with_for_update()
        )
        if organization is None:
            raise OrganizationNotFound
        return organization

    def _membership(
        self,
        organization_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> OrganizationMembership | None:
        return self.session.scalar(
            select(OrganizationMembership).where(
                OrganizationMembership.organization_id == organization_id,
                OrganizationMembership.user_id == user_id,
            )
        )

    def _require_membership(
        self,
        actor_user_id: uuid.UUID,
        organization_id: uuid.UUID,
    ) -> OrganizationMembership:
        membership = self._membership(organization_id, actor_user_id)
        if membership is None:
            # 404 evita revelar a existência de organizações de terceiros.
            raise OrganizationNotFound
        return membership

    def _require_capability(
        self,
        actor_user_id: uuid.UUID,
        organization_id: uuid.UUID,
        capability: Capability,
    ) -> OrganizationMembership:
        membership = self._require_membership(actor_user_id, organization_id)
        if capability not in capabilities_for(membership.role):
            raise Forbidden
        return membership

    def _require_active_user(self, user_id: uuid.UUID) -> User:
        user = self.session.get(User, user_id)
        if user is None:
            raise UserNotFound
        if user.status != "active":
            raise UserNotActive
        return user

    def _ensure_not_last_owner(
        self,
        organization_id: uuid.UUID,
        membership: OrganizationMembership,
    ) -> None:
        if Role(membership.role) != Role.OWNER:
            return
        owners = self.session.scalar(
            select(func.count())
            .select_from(OrganizationMembership)
            .where(
                OrganizationMembership.organization_id == organization_id,
                OrganizationMembership.role == Role.OWNER.value,
            )
        )
        if (owners or 0) <= 1:
            raise LastOwner


def _ensure_can_assign(actor_role: Role, target_role: Role) -> None:
    """Somente o proprietário concede papéis administrativos."""

    if target_role in {Role.OWNER, Role.ADMIN} and actor_role != Role.OWNER:
        raise CannotManageRole


def _ensure_can_manage_target(actor_role: Role, target_role: Role) -> None:
    """Administrador só gerencia operadores que não sejam ele mesmo."""

    if actor_role == Role.ADMIN and target_role != Role.OPERATOR:
        raise CannotManageRole


def _clean_organization_name(value: str) -> str:
    normalized = " ".join(value.split())
    if not 2 <= len(normalized) <= 120:
        raise InvalidInput
    return normalized


def _clean_venue_name(value: str) -> str:
    normalized = " ".join(value.split())
    if not 2 <= len(normalized) <= 120:
        raise InvalidInput
    return normalized


def _clean_optional(value: str | None, *, max_length: int) -> str | None:
    if value is None:
        return None
    normalized = " ".join(value.split())
    if len(normalized) > max_length:
        raise InvalidInput
    return normalized or None


def _clean_state(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = value.strip().upper()
    if len(normalized) != 2 or not normalized.isalpha():
        raise InvalidInput
    return normalized
