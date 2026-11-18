"""Semeia dados de demonstracao de forma idempotente.

Uso (a partir de backend/):

    $env:JOGA_DATABASE_URL="postgresql+psycopg://..."
    $env:JOGA_DEMO_SEED_PASSWORD="<senha-forte>"
    .venv\\Scripts\\python.exe -m scripts.seed_demo

A senha nunca e impressa nem persistida em claro. O hash Argon2id e produzido
pelo PasswordService; a conta passa pelo EmailAccountService, que valida a
politica de senha e cria usuario, credencial de e-mail e perfil na mesma
transacao. Faixas e pacotes usam o pricing.service.
"""

from __future__ import annotations

import os
import sys
import uuid
from datetime import time, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.infrastructure.database.engine import build_engine
from app.modules.email.addresses import hash_email, normalize_email
from app.modules.email.deliveries import EmailDeliveryService
from app.modules.email.models import UserEmail
from app.modules.identity.clock import utcnow
from app.modules.identity.email_accounts import EmailAccountService
from app.modules.identity.email_challenges import EmailChallengeService
from app.modules.identity.models import PhoneChallenge, User, UserPassword
from app.modules.identity.otp import ChallengePurpose
from app.modules.identity.passwords import PasswordPolicyError, PasswordService
from app.modules.organizations.models import Organization, OrganizationVenue
from app.modules.organizations.service import OrganizationService, normalize_cnpj
from app.modules.pricing.service import seed_default_bands
from app.modules.profile.models import Sport
from app.modules.venues.models import VenueSpace
from app.modules.venues.service import VenueService
from app.modules.venues.storage import get_photo_storage

DEMO_PASSWORD_ENV = "JOGA_DEMO_SEED_PASSWORD"

OPERATOR_EMAIL = "operador@demo.joga.test"
OPERATOR_NAME = "Operador Demo"
PLAYER_EMAIL = "jogador@demo.joga.test"
PLAYER_NAME = "Jogador Demo"

ORGANIZATION_NAME = "Arena Demo"
# CNPJ ficticio de teste com digitos verificadores validos. Nao e um CNPJ real.
DEMO_CNPJ = "11222333000181"
VENUE_NAME = "Arena Demo Centro"
SPACE_NAME = "Quadra 1"

AVAILABILITY_START = time(6, 0)
AVAILABILITY_END = time(22, 0)
AVAILABILITY_PRICE_CENTS = 12_000
AVAILABILITY_SLOT_MINUTES = 60


def _active_credential(session: Session, email: str) -> UserEmail | None:
    normalized = normalize_email(email)
    return session.scalar(
        select(UserEmail).where(
            UserEmail.email_normalized == normalized,
            UserEmail.released_at.is_(None),
        )
    )


def _ensure_password(
    session: Session,
    user: User,
    email: str,
    password: str,
    passwords: PasswordService,
) -> str:
    passwords.validate(password, normalize_email(email))
    stored = session.get(UserPassword, user.id)
    if stored is None:
        session.add(
            UserPassword(
                user_id=user.id,
                password_hash=passwords.hash(password),
                password_changed_at=utcnow(),
            )
        )
        return "senha criada"
    if not passwords.verify(stored.password_hash, password):
        stored.password_hash = passwords.hash(password)
        stored.password_changed_at = utcnow()
        return "senha atualizada"
    return "senha preservada"


def _create_user(
    session: Session,
    accounts: EmailAccountService,
    *,
    email: str,
    password: str,
    display_name: str,
) -> User:
    """Cria a conta por um recibo de verificacao sintetico e controlado.

    O recibo dispensa o envio de e-mail no seed, mas a criacao continua dentro
    do EmailAccountService (politica de senha, perfil e hash Argon2id).
    """
    settings = get_settings()
    normalized = normalize_email(email)
    moment = utcnow()
    challenge = PhoneChallenge(
        id=uuid.uuid4(),
        phone_hash=hash_email(normalized, settings.phone_hash_secret.get_secret_value()),
        subject_type="email",
        purpose=ChallengePurpose.email_verification.value,
        code_hash="0" * 64,
        attempts=1,
        max_attempts=settings.otp_max_attempts,
        expires_at=moment + timedelta(seconds=settings.otp_receipt_ttl_seconds),
        consumed_at=moment,
        created_at=moment,
    )
    session.add(challenge)
    session.flush()

    account = accounts.register(
        challenge.id,
        normalized,
        password,
        display_name=display_name,
        now=moment,
    )
    user = session.get(User, account.id)
    if user is None:  # pragma: no cover - defensivo; register acabou de criar
        raise RuntimeError("conta criada nao encontrada")
    return user


def _ensure_user(
    session: Session,
    accounts: EmailAccountService,
    passwords: PasswordService,
    *,
    email: str,
    password: str,
    display_name: str,
) -> tuple[User, str]:
    credential = _active_credential(session, email)
    if credential is None:
        user = _create_user(
            session,
            accounts,
            email=email,
            password=password,
            display_name=display_name,
        )
        return user, "criado"

    user = session.get(User, credential.user_id)
    if user is None or user.status != "active":
        raise RuntimeError(f"credencial de {email} sem usuario ativo")
    return user, _ensure_password(session, user, email, password, passwords)


def _ensure_organization(session: Session, owner_id: uuid.UUID) -> Organization:
    service = OrganizationService(session)
    existing = session.scalar(select(Organization).where(Organization.name == ORGANIZATION_NAME))
    if existing is not None:
        member_ids = {access.organization.id for access in service.list_for_user(owner_id)}
        if existing.id not in member_ids:
            raise RuntimeError(
                f"a organizacao {ORGANIZATION_NAME!r} existe sem vinculo do operador"
            )
        organization = existing
    else:
        organization = service.create(owner_id, ORGANIZATION_NAME)

    document = normalize_cnpj(DEMO_CNPJ)
    if organization.legal_document != document:
        organization.legal_document = document
        session.flush()
    return organization


def _ensure_venue(
    session: Session,
    owner_id: uuid.UUID,
    organization_id: uuid.UUID,
) -> OrganizationVenue:
    service = OrganizationService(session)
    for venue in service.list_venues(owner_id, organization_id):
        if venue.name == VENUE_NAME:
            return venue
    return service.create_venue(
        owner_id,
        organization_id,
        name=VENUE_NAME,
        city="Sao Paulo",
        state="SP",
        address_line="Rua da Demo, 100",
        latitude=-23.5505,
        longitude=-46.6333,
        postal_code="01001000",
        geocoding_precision="manual",
        timezone="America/Sao_Paulo",
    )


def _ensure_space(
    session: Session,
    owner_id: uuid.UUID,
    organization_id: uuid.UUID,
    venue_id: uuid.UUID,
) -> VenueSpace:
    service = VenueService(session, get_photo_storage())
    record = next(
        (
            item
            for item in service.list_spaces(owner_id, organization_id, venue_id)
            if item.space.name == SPACE_NAME
        ),
        None,
    )
    if record is not None:
        space = record.space
        sports = list(record.sports)
    else:
        space = service.create_space(
            owner_id,
            organization_id,
            venue_id,
            name=SPACE_NAME,
            description="Quadra de demonstracao do JOGA",
            is_covered=False,
        )
        sports = []

    football = session.scalar(select(Sport).where(Sport.slug == "futebol", Sport.active.is_(True)))
    if football is not None and football not in sports:
        service.replace_sports(
            owner_id,
            organization_id,
            venue_id,
            space.id,
            [sport.id for sport in [*sports, football]],
        )
    return space


def _ensure_availability(
    session: Session,
    owner_id: uuid.UUID,
    organization_id: uuid.UUID,
    venue_id: uuid.UUID,
    space_id: uuid.UUID,
) -> int:
    service = VenueService(session, get_photo_storage())
    existing = {
        row.weekday
        for row in service.list_availability(owner_id, organization_id, venue_id, space_id)
    }
    created = 0
    for weekday in range(1, 8):
        if weekday in existing:
            continue
        service.create_availability(
            owner_id,
            organization_id,
            venue_id,
            space_id,
            weekday=weekday,
            start_time=AVAILABILITY_START,
            end_time=AVAILABILITY_END,
            price_cents=AVAILABILITY_PRICE_CENTS,
            slot_minutes=AVAILABILITY_SLOT_MINUTES,
        )
        created += 1
    return created


def main() -> int:
    settings = get_settings()
    secret = settings.phone_hash_secret.get_secret_value()
    password = os.environ.get(DEMO_PASSWORD_ENV, "")
    if not password:
        print(f"erro: defina {DEMO_PASSWORD_ENV}", file=sys.stderr)
        return 2

    passwords = PasswordService()
    for email in (OPERATOR_EMAIL, PLAYER_EMAIL):
        try:
            passwords.validate(password, normalize_email(email))
        except PasswordPolicyError:
            print(
                "erro: a senha do seed nao atende a politica (minimo 10, "
                "sem senha comum e diferente do e-mail)",
                file=sys.stderr,
            )
            return 2

    engine = build_engine(settings)
    try:
        with Session(engine) as session:
            deliveries = EmailDeliveryService(
                session,
                provider=settings.email_provider,
                daily_budget=settings.email_daily_budget,
                secret=secret,
                max_attempts=settings.email_max_delivery_attempts,
                bounce_threshold=settings.email_bounce_threshold,
            )
            challenges = EmailChallengeService(session, deliveries, secret)
            accounts = EmailAccountService(
                session,
                challenges,
                deliveries,
                passwords,
                secret,
                receipt_ttl_seconds=settings.otp_receipt_ttl_seconds,
            )

            seed_default_bands(session)

            operator, operator_state = _ensure_user(
                session,
                accounts,
                passwords,
                email=OPERATOR_EMAIL,
                password=password,
                display_name=OPERATOR_NAME,
            )
            player, player_state = _ensure_user(
                session,
                accounts,
                passwords,
                email=PLAYER_EMAIL,
                password=password,
                display_name=PLAYER_NAME,
            )

            organization = _ensure_organization(session, operator.id)
            venue = _ensure_venue(session, operator.id, organization.id)
            space = _ensure_space(session, operator.id, organization.id, venue.id)
            availability_created = _ensure_availability(
                session,
                operator.id,
                organization.id,
                venue.id,
                space.id,
            )

            session.commit()

            print("Seed de demonstracao concluido.")
            print(f"Operador: {OPERATOR_EMAIL} id={operator.id} ({operator_state})")
            print(f"Jogador: {PLAYER_EMAIL} id={player.id} ({player_state})")
            print(f"Organizacao: {organization.name} id={organization.id} role=OWNER")
            print(f"Estabelecimento: {venue.name} id={venue.id}")
            print(f"Quadra: {space.name} id={space.id}")
            print(
                "Disponibilidade: seg-dom 06:00-22:00, "
                f"preco={AVAILABILITY_PRICE_CENTS} centavos, "
                f"slot={AVAILABILITY_SLOT_MINUTES} min, "
                f"janelas_criadas={availability_created}"
            )
            print(f"Senha: definida por {DEMO_PASSWORD_ENV} (nao impressa).")
    finally:
        engine.dispose()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
