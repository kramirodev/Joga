"""Ingestão de erros do cliente (Fase 3, ADR 0078)."""

from __future__ import annotations

import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.infrastructure.database.dependency import get_session
from app.main import create_app
from app.modules.observability.models import LogEvent
from app.modules.observability.service import LogEntry
from tests.helpers_results import make_token, make_user

IP = "203.0.113.10"
PATH = "/api/v1/observability/client-events"


def obs_settings(**overrides: Any) -> Settings:
    values: dict[str, Any] = {
        "_env_file": None,
        "environment": "test",
        "observability_enabled": True,
        "log_http_success_sample_rate": 0.0,
        "log_stacktraces": True,
        "log_max_export_rows": 20_000,
    }
    values.update(overrides)
    return Settings(**values)


class DbDispatcher:
    """Dispatcher síncrono de teste: grava direto na sessão SQLite."""

    def __init__(self, session: Session, settings: Settings) -> None:
        self.session = session
        self.settings = settings
        self.security: list[dict[str, Any]] = []

    def submit(self, entry: LogEntry) -> None:
        self.session.add(entry.to_model())
        self.session.commit()

    def write_security_now(self, event_type: str, **kwargs: Any) -> None:
        self.security.append({"event_type": event_type, **kwargs})


@contextmanager
def build_client(
    db_session: Session,
    settings: Settings,
    *,
    client_ip: str = IP,
    dispatcher: DbDispatcher | None = None,
) -> Iterator[TestClient]:
    app = create_app(settings)

    def override_session() -> Iterator[Session]:
        yield db_session

    app.dependency_overrides[get_session] = override_session
    app.dependency_overrides[get_settings] = lambda: settings
    with TestClient(app, client=(client_ip, 50_000)) as client:
        if dispatcher is not None:
            client.app.state.observability = dispatcher
        yield client


def client_entries(session: Session) -> list[LogEvent]:
    return list(session.scalars(select(LogEvent).where(LogEvent.category == "client")))


def event_payload(**overrides: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "level": "error",
        "message": "falha ao carregar lista",
        "platform": "web",
        "app_version": "1.2.3",
    }
    payload.update(overrides)
    return payload


def test_valid_batch_is_persisted_with_request_context(db_session: Session) -> None:
    dispatcher = DbDispatcher(db_session, obs_settings())
    with build_client(db_session, obs_settings(), dispatcher=dispatcher) as client:
        response = client.post(
            PATH,
            json={
                "events": [
                    event_payload(
                        module="painel.dashboard",
                        error_code="DASH_500",
                        screen="/admin/x?tab=1#top",
                        build="77",
                        request_id="req-cliente-1",
                        stack="Traceback: boom",
                    )
                ]
            },
        )
    assert response.status_code == 202, response.text
    assert response.json() == {"accepted": 1, "dropped": 0}

    rows = client_entries(db_session)
    assert len(rows) == 1
    row = rows[0]
    assert row.level == "error"
    assert row.category == "client"
    assert row.module == "painel.dashboard"
    assert row.error_code == "DASH_500"
    assert row.ip == IP
    assert row.endpoint is None
    assert row.request_id == "req-cliente-1"
    assert row.stack == "Traceback: boom"
    assert row.details == {
        "platform": "web",
        "version": "1.2.3",
        "screen": "/admin/x",
        "build": "77",
    }


def test_message_and_stack_are_masked(db_session: Session) -> None:
    email = "pessoa@example.com"
    phone = "+55 11 99999-9999"
    token = "segredo" + "-token-123"
    dispatcher = DbDispatcher(db_session, obs_settings())
    with build_client(db_session, obs_settings(), dispatcher=dispatcher) as client:
        response = client.post(
            PATH,
            json={
                "events": [
                    event_payload(
                        message=f"falhou para {email} tel {phone} token={token}",
                        stack=f"Traceback ... token={token} contato {email}",
                    )
                ]
            },
        )
    assert response.status_code == 202, response.text

    row = client_entries(db_session)[0]
    assert row.message is not None
    assert row.stack is not None
    for secret in (email, phone, token):
        assert secret not in row.message
        assert secret not in row.stack


def test_screen_is_normalized_and_invalid_screen_is_discarded(db_session: Session) -> None:
    dispatcher = DbDispatcher(db_session, obs_settings())
    with build_client(db_session, obs_settings(), dispatcher=dispatcher) as client:
        response = client.post(
            PATH,
            json={
                "events": [
                    event_payload(screen="/admin/x?email=a@b.com"),
                    event_payload(screen="admin/sem-barra"),
                ]
            },
        )
    assert response.status_code == 202, response.text
    assert response.json() == {"accepted": 2, "dropped": 0}

    screens = {(row.details or {}).get("screen") for row in client_entries(db_session)}
    assert screens == {None, "/admin/x"}


def test_identity_fields_in_payload_are_ignored(db_session: Session) -> None:
    forged_user = str(uuid.uuid4())
    dispatcher = DbDispatcher(db_session, obs_settings())
    with build_client(db_session, obs_settings(), dispatcher=dispatcher) as client:
        response = client.post(
            PATH,
            json={
                "events": [
                    event_payload(
                        user_id=forged_user,
                        ip="10.0.0.1",
                        details={"free": "text"},
                        email="pessoa@example.com",
                    )
                ]
            },
        )
    assert response.status_code == 202, response.text

    row = client_entries(db_session)[0]
    assert row.user_id is None
    assert row.ip == IP
    assert set((row.details or {}).keys()) == {"platform", "version", "screen", "build"}


def test_batch_limits_and_disabled_observability(db_session: Session) -> None:
    dispatcher = DbDispatcher(db_session, obs_settings())
    with build_client(db_session, obs_settings(), dispatcher=dispatcher) as client:
        too_many = client.post(PATH, json={"events": [event_payload() for _ in range(21)]})
        empty = client.post(PATH, json={"events": []})
    assert too_many.status_code == 422
    assert empty.status_code == 422
    assert client_entries(db_session) == []

    disabled_settings = obs_settings(observability_enabled=False)
    with build_client(db_session, disabled_settings) as client:
        disabled = client.post(PATH, json={"events": [event_payload()]})
    assert disabled.status_code == 202
    assert client_entries(db_session) == []


def test_rate_limit_returns_429_with_retry_after(db_session: Session) -> None:
    settings = obs_settings(client_events_rate_limit_per_minute=1)
    dispatcher = DbDispatcher(db_session, settings)
    with build_client(db_session, settings, dispatcher=dispatcher) as client:
        first = client.post(PATH, json={"events": [event_payload()]})
        limited = client.post(PATH, json={"events": [event_payload()]})
    assert first.status_code == 202
    assert limited.status_code == 429
    assert limited.json() == {"detail": {"code": "rate_limited"}}
    assert limited.headers["Retry-After"]
    assert dispatcher.security[-1]["event_type"] == "http.rate_limited"


def test_admin_listing_masks_client_event_ip(db_session: Session) -> None:
    admin_id = make_user(db_session)
    settings = obs_settings(platform_admins=str(admin_id))
    dispatcher = DbDispatcher(db_session, settings)
    with build_client(db_session, settings, dispatcher=dispatcher) as client:
        posted = client.post(PATH, json={"events": [event_payload()]})
        assert posted.status_code == 202
        headers = {"Authorization": f"Bearer {make_token(db_session, admin_id)}"}
        listing = client.get(
            "/api/v1/admin/observability/events",
            params={"category": "client"},
            headers=headers,
        )
    assert listing.status_code == 200, listing.text
    events = listing.json()["events"]
    assert len(events) == 1
    assert events[0]["category"] == "client"
    assert events[0]["ip_masked"] is True
    assert events[0]["ip"] == "203.0.113.\u2022"
    assert events[0]["ip"] != IP


def test_response_never_fails_when_dispatcher_raises(db_session: Session) -> None:
    class BrokenDispatcher(DbDispatcher):
        def submit(self, entry: LogEntry) -> None:
            raise RuntimeError("dispatcher fora do ar")

    settings = obs_settings()
    dispatcher = BrokenDispatcher(db_session, settings)
    with build_client(db_session, settings, dispatcher=dispatcher) as client:
        response = client.post(PATH, json={"events": [event_payload()]})
    assert response.status_code == 202
    assert response.json() == {"accepted": 0, "dropped": 1}
    assert client_entries(db_session) == []


@pytest.mark.parametrize("level", ("debug", "info", "warn", "error", "fatal"))
def test_accepted_levels(db_session: Session, level: str) -> None:
    dispatcher = DbDispatcher(db_session, obs_settings())
    with build_client(db_session, obs_settings(), dispatcher=dispatcher) as client:
        response = client.post(PATH, json={"events": [event_payload(level=level)]})
    assert response.status_code == 202, response.text
    assert client_entries(db_session)[0].level == level
