"""Testes do serviço de passkeys com autenticador sintético."""

from collections.abc import Iterator
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.infrastructure.database.base import Base
from app.modules.identity.models import User
from app.modules.identity.passkeys import (
    InvalidPasskeyChallenge,
    PasskeyAlreadyRegistered,
    PasskeyNotFound,
    PasskeyRateLimited,
    PasskeyService,
    PasskeyVerificationFailed,
)
from tests.webauthn_authenticator import SoftAuthenticator

RP_ID = "joga-passkeys.vercel.app"
ORIGIN = "android:apk-key-hash:-sYXRdwJA3hvue3mKpYrOZ9zSPC7b4mbgzJmdZEDO5w"
WEB_ORIGIN = "https://joga-passkeys.vercel.app"
BASE_TIME = datetime(2026, 11, 3, 12, 0, tzinfo=UTC)


@pytest.fixture
def session() -> Iterator[Session]:
    engine = create_engine(
        "sqlite+pysqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    with Session(engine) as database_session:
        yield database_session
    Base.metadata.drop_all(engine)
    engine.dispose()


def make_user(session: Session) -> User:
    user = User(status="active")
    session.add(user)
    session.flush()
    return user


def build_service(session: Session) -> PasskeyService:
    return PasskeyService(
        session,
        rp_id=RP_ID,
        rp_name="JOGA",
        origins=[ORIGIN, WEB_ORIGIN],
        challenge_ttl_seconds=300,
    )


def register_credential(
    session: Session,
    user: User,
    authenticator: SoftAuthenticator,
) -> str:
    service = build_service(session)
    options = service.begin_registration(user.id, now=BASE_TIME)
    credential = authenticator.registration_credential(options.public_key["challenge"])
    result = service.finish_registration(
        user.id,
        options.challenge_id,
        credential,
        now=BASE_TIME + timedelta(seconds=1),
    )
    return result.credential_id


def test_registration_and_authentication_happy_path(session: Session) -> None:
    user = make_user(session)
    authenticator = SoftAuthenticator(
        rp_id=RP_ID,
        origin=ORIGIN,
        user_handle=user.id.bytes,
    )
    service = build_service(session)

    options = service.begin_registration(user.id, now=BASE_TIME)
    assert options.public_key["rp"]["id"] == RP_ID
    assert options.public_key["user"]["id"]

    registration = authenticator.registration_credential(options.public_key["challenge"])
    result = service.finish_registration(
        user.id,
        options.challenge_id,
        registration,
        name="Celular",
        now=BASE_TIME + timedelta(seconds=1),
    )
    assert result.name == "Celular"
    assert len(service.list_credentials(user.id)) == 1

    auth_options = service.begin_authentication(
        user_id=user.id,
        now=BASE_TIME + timedelta(seconds=2),
    )
    assertion = authenticator.authentication_credential(auth_options.public_key["challenge"])
    authenticated = service.finish_authentication(
        auth_options.challenge_id,
        assertion,
        now=BASE_TIME + timedelta(seconds=3),
    )

    assert authenticated.user_id == user.id
    assert authenticated.credential_id == result.credential_id


def test_discoverable_authentication_without_user(session: Session) -> None:
    user = make_user(session)
    authenticator = SoftAuthenticator(rp_id=RP_ID, origin=ORIGIN, user_handle=user.id.bytes)
    credential_id = register_credential(session, user, authenticator)
    service = build_service(session)

    options = service.begin_authentication(now=BASE_TIME + timedelta(seconds=2))
    assertion = authenticator.authentication_credential(options.public_key["challenge"])
    authenticated = service.finish_authentication(
        options.challenge_id,
        assertion,
        now=BASE_TIME + timedelta(seconds=3),
    )

    assert authenticated.user_id == user.id
    assert authenticated.credential_id == credential_id


def test_registration_rejects_wrong_origin(session: Session) -> None:
    user = make_user(session)
    authenticator = SoftAuthenticator(
        rp_id=RP_ID,
        origin="https://evil.example",
        user_handle=user.id.bytes,
    )
    service = build_service(session)
    options = service.begin_registration(user.id, now=BASE_TIME)
    credential = authenticator.registration_credential(options.public_key["challenge"])

    with pytest.raises(PasskeyVerificationFailed):
        service.finish_registration(
            user.id,
            options.challenge_id,
            credential,
            now=BASE_TIME + timedelta(seconds=1),
        )


def test_registration_rejects_expired_challenge(session: Session) -> None:
    user = make_user(session)
    authenticator = SoftAuthenticator(rp_id=RP_ID, origin=ORIGIN, user_handle=user.id.bytes)
    service = build_service(session)
    options = service.begin_registration(user.id, now=BASE_TIME)
    credential = authenticator.registration_credential(options.public_key["challenge"])

    with pytest.raises(InvalidPasskeyChallenge):
        service.finish_registration(
            user.id,
            options.challenge_id,
            credential,
            now=BASE_TIME + timedelta(seconds=301),
        )


def test_registration_rejects_replay(session: Session) -> None:
    user = make_user(session)
    authenticator = SoftAuthenticator(rp_id=RP_ID, origin=ORIGIN, user_handle=user.id.bytes)
    service = build_service(session)
    options = service.begin_registration(user.id, now=BASE_TIME)
    credential = authenticator.registration_credential(options.public_key["challenge"])
    service.finish_registration(
        user.id,
        options.challenge_id,
        credential,
        now=BASE_TIME + timedelta(seconds=1),
    )

    with pytest.raises(InvalidPasskeyChallenge):
        service.finish_registration(
            user.id,
            options.challenge_id,
            credential,
            now=BASE_TIME + timedelta(seconds=2),
        )


def test_registration_rejects_duplicate_credential(session: Session) -> None:
    user = make_user(session)
    authenticator = SoftAuthenticator(rp_id=RP_ID, origin=ORIGIN, user_handle=user.id.bytes)
    service = build_service(session)
    first = service.begin_registration(user.id, now=BASE_TIME)
    first_credential = authenticator.registration_credential(first.public_key["challenge"])
    service.finish_registration(
        user.id,
        first.challenge_id,
        first_credential,
        now=BASE_TIME + timedelta(seconds=1),
    )

    second = service.begin_registration(user.id, now=BASE_TIME + timedelta(seconds=2))
    second_credential = authenticator.registration_credential(second.public_key["challenge"])
    with pytest.raises(PasskeyAlreadyRegistered):
        service.finish_registration(
            user.id,
            second.challenge_id,
            second_credential,
            now=BASE_TIME + timedelta(seconds=3),
        )


def test_registration_rejects_challenge_from_other_user(session: Session) -> None:
    owner = make_user(session)
    other = make_user(session)
    authenticator = SoftAuthenticator(
        rp_id=RP_ID,
        origin=ORIGIN,
        user_handle=owner.id.bytes,
    )
    service = build_service(session)
    options = service.begin_registration(owner.id, now=BASE_TIME)
    credential = authenticator.registration_credential(options.public_key["challenge"])

    with pytest.raises(InvalidPasskeyChallenge):
        service.finish_registration(
            other.id,
            options.challenge_id,
            credential,
            now=BASE_TIME + timedelta(seconds=1),
        )


def test_revoked_credential_cannot_authenticate(session: Session) -> None:
    user = make_user(session)
    authenticator = SoftAuthenticator(rp_id=RP_ID, origin=ORIGIN, user_handle=user.id.bytes)
    credential_id = register_credential(session, user, authenticator)
    service = build_service(session)
    service.revoke_credential(user.id, credential_id)
    assert service.list_credentials(user.id) == []

    options = service.begin_authentication(user_id=user.id, now=BASE_TIME + timedelta(seconds=2))
    assertion = authenticator.authentication_credential(options.public_key["challenge"])

    with pytest.raises(PasskeyNotFound):
        service.finish_authentication(
            options.challenge_id,
            assertion,
            now=BASE_TIME + timedelta(seconds=3),
        )


def test_sign_count_regression_is_rejected(session: Session) -> None:
    user = make_user(session)
    authenticator = SoftAuthenticator(rp_id=RP_ID, origin=ORIGIN, user_handle=user.id.bytes)
    register_credential(session, user, authenticator)
    service = build_service(session)

    first = service.begin_authentication(user_id=user.id, now=BASE_TIME + timedelta(seconds=2))
    first_assertion = authenticator.authentication_credential(
        first.public_key["challenge"],
        sign_count=1,
    )
    service.finish_authentication(
        first.challenge_id,
        first_assertion,
        now=BASE_TIME + timedelta(seconds=3),
    )

    second = service.begin_authentication(user_id=user.id, now=BASE_TIME + timedelta(seconds=3))
    repeated = authenticator.authentication_credential(
        second.public_key["challenge"],
        sign_count=1,
    )
    with pytest.raises(PasskeyVerificationFailed):
        service.finish_authentication(
            second.challenge_id,
            repeated,
            now=BASE_TIME + timedelta(seconds=4),
        )


def test_begin_registration_respects_ip_hourly_limit(session: Session) -> None:
    user = make_user(session)
    service = PasskeyService(
        session,
        rp_id=RP_ID,
        rp_name="JOGA",
        origins=[ORIGIN, WEB_ORIGIN],
        challenge_ttl_seconds=300,
        max_per_ip_per_hour=1,
    )

    service.begin_registration(
        user.id,
        now=BASE_TIME,
        request_ip_hash="a" * 64,
    )
    with pytest.raises(PasskeyRateLimited):
        service.begin_registration(
            user.id,
            now=BASE_TIME + timedelta(seconds=1),
            request_ip_hash="a" * 64,
        )
