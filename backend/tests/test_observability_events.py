"""Observabilidade Fase 1: HTTP, redação, segurança e admin (ADR 0078)."""

from __future__ import annotations

import asyncio
import json
import uuid
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.infrastructure.database.dependency import get_session
from app.main import create_app
from app.modules.identity.models import AuditLog, SecurityEvent
from app.modules.identity.phone import hash_ip
from app.modules.moderation.models import ModerationOperator
from app.modules.observability.models import LogEvent
from app.modules.observability.redaction import MAX_METADATA_BYTES, mask_ip
from app.modules.observability.service import (
    LogDispatcher,
    LogEntry,
    build_entry,
    log_job,
)
from tests.helpers_results import make_token, make_user

IP = "203.0.113.10"
FORGED = ("10.0.0.1", "10.0.0.2")


class MemoryDispatcher:
    """Dispatcher de teste: registra entradas em memória, sem banco."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.entries: list[LogEntry] = []
        self.security: list[dict[str, Any]] = []

    def submit(self, entry: LogEntry) -> None:
        self.entries.append(entry)

    def write_security_now(self, event_type: str, **kwargs: Any) -> None:
        self.security.append({"event_type": event_type, **kwargs})


def obs_settings(**overrides: Any) -> Settings:
    values: dict[str, Any] = {
        "_env_file": None,
        "environment": "test",
        "observability_enabled": False,
        "log_http_success_sample_rate": 1.0,
        "log_stacktraces": True,
        "log_max_export_rows": 20_000,
    }
    values.update(overrides)
    return Settings(**values)


def _ok() -> dict[str, bool]:
    return {"ok": True}


def _boom() -> None:
    raise RuntimeError("falhou password=segredo123 email pessoa@example.com")


def build_client(
    db_session: Session,
    settings: Settings,
    *,
    client_ip: str = IP,
) -> TestClient:
    app = create_app(settings)
    app.add_api_route("/api/v1/_test/ok", _ok, methods=["GET"])
    app.add_api_route("/api/v1/_test/boom", _boom, methods=["GET"])

    def override_session() -> Iterator[Session]:
        yield db_session

    app.dependency_overrides[get_session] = override_session
    app.dependency_overrides[get_settings] = lambda: settings
    return TestClient(app, client=(client_ip, 50_000))


@pytest.fixture
def memory(db_session: Session) -> Iterator[tuple[TestClient, MemoryDispatcher]]:
    dispatcher = MemoryDispatcher(obs_settings(log_http_success_sample_rate=1.0))
    with build_client(db_session, obs_settings()) as client:
        client.app.state.observability = dispatcher
        yield client, dispatcher


def add_log(
    session: Session,
    *,
    occurred_at: datetime,
    level: str = "info",
    category: str = "http",
    message: str = "evento",
    ip: str | None = IP,
    user_id: uuid.UUID | None = None,
    status: int | None = 200,
    request_id: str | None = None,
    stack: str | None = None,
    details: dict[str, Any] | None = None,
) -> LogEvent:
    event = LogEvent(
        occurred_at=occurred_at,
        level=level,
        category=category,
        module="test",
        message=message,
        ip=ip,
        ip_hash=hash_ip(ip, "local-development-only-change-me") if ip else None,
        user_id=user_id,
        status=status,
        request_id=request_id,
        stack=stack,
        details=details,
    )
    session.add(event)
    session.commit()
    return event


def admin_headers(session: Session, user_id: uuid.UUID) -> dict[str, str]:
    return {"Authorization": f"Bearer {make_token(session, user_id)}"}


# -- middleware HTTP ------------------------------------------------------
def test_success_is_sampled_and_errors_always_recorded(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Evita que a primeira chamada (cold start) seja classificada como lenta e
    # gravada fora da amostragem; o teste de lentidão é comportamental e não
    # depende do tempo real da suíte.
    monkeypatch.setattr("app.core.observability.SLOW_REQUEST_MS", 10**9)
    dispatcher = MemoryDispatcher(obs_settings(log_http_success_sample_rate=0.0))
    with build_client(db_session, obs_settings()) as client:
        client.app.state.observability = dispatcher
        assert client.get("/api/v1/_test/ok").status_code == 200
        assert dispatcher.entries == []

        assert client.get("/api/v1/_test/missing").status_code == 404
        assert dispatcher.entries[-1].status == 404
        assert dispatcher.entries[-1].level == "warn"

        assert client.get("/api/v1/_test/boom").status_code == 500
        assert [entry.status for entry in dispatcher.entries if entry.category == "http"][-1] == 500

    dispatcher.settings = obs_settings(log_http_success_sample_rate=1.0)
    with build_client(db_session, obs_settings()) as client:
        client.app.state.observability = dispatcher
        dispatcher.entries.clear()
        assert client.get("/api/v1/_test/ok").status_code == 200
        assert len(dispatcher.entries) == 1
        assert dispatcher.entries[0].status == 200
        assert dispatcher.entries[0].endpoint == "/api/v1/_test/ok"


def test_exception_has_stack_and_never_leaks_to_response(
    db_session: Session, caplog: pytest.LogCaptureFixture
) -> None:
    dispatcher = MemoryDispatcher(obs_settings(log_http_success_sample_rate=1.0))
    with caplog.at_level("DEBUG"):
        with build_client(db_session, obs_settings()) as client:
            client.app.state.observability = dispatcher
            response = client.get("/api/v1/_test/boom")

    assert "segredo123" not in caplog.text
    assert "pessoa@example.com" not in caplog.text

    assert response.status_code == 500
    assert response.json() == {"detail": {"code": "internal_error"}}
    assert "segredo123" not in response.text
    assert "pessoa@example.com" not in response.text

    app_entries = [entry for entry in dispatcher.entries if entry.stack is not None]
    assert len(app_entries) == 1
    entry = app_entries[0]
    assert entry.category == "app"
    assert entry.level == "error"
    assert entry.error_code == "RuntimeError"
    assert entry.stack is not None and "RuntimeError" in entry.stack
    assert "segredo123" not in entry.stack
    assert "password=[redacted]" in entry.stack
    assert entry.message is not None and "password=[redacted]" in entry.message
    assert "pessoa@example.com" not in entry.message


def test_security_events_capture_ip_and_request_id(db_session: Session) -> None:
    dispatcher = MemoryDispatcher(obs_settings(log_http_success_sample_rate=1.0))
    with build_client(db_session, obs_settings()) as client:
        client.app.state.observability = dispatcher
        response = client.get("/api/v1/auth/me", headers={"Authorization": "Bearer token-invalido"})

    assert response.status_code == 401
    assert len(dispatcher.security) == 1
    event = dispatcher.security[0]
    assert event["event_type"] == "http.unauthorized"
    assert event["ip"] == IP
    assert event["ip_hash"] == hash_ip(IP, "local-development-only-change-me")
    assert event["request_id"] == response.headers["X-Request-ID"]
    assert event["result"] == "failure"


def test_forbidden_is_security_event(db_session: Session) -> None:
    dispatcher = MemoryDispatcher(obs_settings(log_http_success_sample_rate=1.0))
    user_id = make_user(db_session)
    with build_client(db_session, obs_settings(platform_admins="")) as client:
        client.app.state.observability = dispatcher
        response = client.get("/api/v1/admin/users", headers=admin_headers(db_session, user_id))

    assert response.status_code == 403
    assert dispatcher.security[-1]["event_type"] == "http.forbidden"
    assert dispatcher.security[-1]["user_id"] == user_id


def test_real_ip_ignores_forged_forwarding_headers(db_session: Session) -> None:
    dispatcher = MemoryDispatcher(obs_settings(log_http_success_sample_rate=1.0))
    real_ip = "198.51.100.7"
    with build_client(db_session, obs_settings(), client_ip=real_ip) as client:
        client.app.state.observability = dispatcher
        client.get(
            "/api/v1/_test/ok",
            headers={
                "X-Forwarded-For": FORGED[0],
                "CF-Connecting-IP": FORGED[1],
                "True-Client-IP": FORGED[1],
                "User-Agent": "pytest-agent",
            },
        )

    entry = dispatcher.entries[-1]
    assert entry.ip == real_ip
    assert entry.ip_hash == hash_ip(real_ip, "local-development-only-change-me")
    assert entry.user_agent == "pytest-agent"
    serialized = f"{entry.ip} {entry.as_stdout()}"
    assert FORGED[0] not in serialized
    assert FORGED[1] not in serialized


def test_health_is_not_persisted(db_session: Session) -> None:
    dispatcher = MemoryDispatcher(obs_settings(log_http_success_sample_rate=1.0))
    with build_client(db_session, obs_settings()) as client:
        client.app.state.observability = dispatcher
        assert client.get("/api/v1/health/live").status_code == 200
    assert dispatcher.entries == []


# -- redação --------------------------------------------------------------
def test_redaction_of_secrets_and_pii() -> None:
    entry = build_entry(
        level="info",
        category="app",
        message=(
            "password=abc123 token: xyz otp=123456 code=654321 "
            "Bearer abcdefghij.klmnopqrst.uvwxyz123456 "
            "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.abcdefghijklmnop "
            "contato pessoa@example.com cpf 123.456.789-09 tel +55 11 98765-4321"
        ),
        details={
            "password": "abc123",
            "access_token": "tok",
            "cookie": "session=1",
            "nested": {"otp": "999999", "safe": "ok"},
            "email": "pessoa@example.com",
            "note": "Bearer abcdefghij.klmnopqrst.uvwxyz123456",
        },
        user_agent="a" * 600,
        use_request_context=False,
    )
    message = entry.message or ""
    assert "abc123" not in message
    assert "xyz" not in message
    assert "123456" not in message
    assert "abcdefghij.klmnopqrst" not in message
    assert "eyJhbGci" not in message
    assert "pessoa@example.com" not in message
    assert "p***@example.com" in message
    assert "123.456.789-09" not in message
    assert "98765-4321" not in message
    assert entry.details is not None
    assert entry.details["password"] == "[redacted]"
    assert entry.details["access_token"] == "[redacted]"
    assert entry.details["cookie"] == "[redacted]"
    assert entry.details["nested"] == {"otp": "[redacted]", "safe": "ok"}
    assert entry.details["email"] == "p***@example.com"
    assert "abcdefghij.klmnopqrst" not in str(entry.details["note"])
    assert entry.user_agent is not None and len(entry.user_agent) == 512


def test_identifiers_are_not_corrupted_by_pii_masking() -> None:
    identifiers = [
        "7c457778-2607-42c0-a473-065ff7beab96",  # disparava o padrão de telefone
        "09397a75-3b2c-4a43-ac7d-b22887587284",  # disparava o padrão de CPF
        "x12345678901",
    ]
    entry = build_entry(
        level="info",
        category="audit",
        message="ids " + " ".join(identifiers),
        details={"invite_id": identifiers[0], "other_id": identifiers[1]},
        use_request_context=False,
    )
    assert entry.details == {
        "invite_id": identifiers[0],
        "other_id": identifiers[1],
    }
    assert entry.message is not None
    for identifier in identifiers:
        assert identifier in entry.message


def test_metadata_and_message_are_bounded() -> None:
    entry = build_entry(
        level="info",
        category="app",
        message="x" * 5_000,
        details={"payload": "y" * (MAX_METADATA_BYTES * 2)},
        use_request_context=False,
    )
    assert entry.message is not None and len(entry.message) == 2_048
    assert entry.details is not None and entry.details.get("_truncated") is True


def test_ip_masking_helpers() -> None:
    assert mask_ip("203.0.113.10") == "203.0.113.•"
    assert mask_ip("2001:db8:1234:5678::1") == "2001:db8:1234:•"
    assert mask_ip(None) is None


# -- dispatcher -----------------------------------------------------------
def test_dispatcher_batches_and_flushes() -> None:
    captured: list[LogEntry] = []
    settings = obs_settings(observability_enabled=True, log_async_queue_size=100)
    dispatcher = LogDispatcher(
        settings,
        session_factory=None,
        sink=captured.extend,
        flush_interval_seconds=0.01,
        batch_size=2,
    )

    async def scenario() -> None:
        await dispatcher.start()
        for index in range(5):
            dispatcher.submit(
                build_entry(
                    level="info",
                    category="job",
                    message=f"evento {index}",
                    use_request_context=False,
                )
            )
        await dispatcher.flush()
        await dispatcher.stop()

    asyncio.run(scenario())
    assert len(captured) == 5
    assert dispatcher.written == 5


def test_database_failure_falls_back_and_counts_loss(
    caplog: pytest.LogCaptureFixture,
) -> None:
    def failing_factory() -> Session:
        raise RuntimeError("banco indisponível")

    settings = obs_settings(observability_enabled=True, log_async_queue_size=100)
    dispatcher = LogDispatcher(settings, session_factory=failing_factory)
    entry = build_entry(
        level="error",
        category="app",
        message="falha",
        use_request_context=False,
    )
    with caplog.at_level("ERROR", logger="joga.observability"):
        dispatcher.submit_sync(entry)

    assert dispatcher.failed_batches == 1
    assert dispatcher.written == 0
    assert any("log_events_fallback" in record.message for record in caplog.records)


def test_request_survives_dispatcher_failure(db_session: Session) -> None:
    class BrokenDispatcher(MemoryDispatcher):
        def submit(self, entry: LogEntry) -> None:
            raise RuntimeError("fila quebrada")

        def write_security_now(self, event_type: str, **kwargs: Any) -> None:
            raise RuntimeError("banco quebrado")

    dispatcher = BrokenDispatcher(obs_settings(log_http_success_sample_rate=1.0))
    with build_client(db_session, obs_settings()) as client:
        client.app.state.observability = dispatcher
        response = client.get("/api/v1/_test/ok")
    assert response.status_code == 200


def test_log_job_writes_operational_event(db_session: Session) -> None:
    log_job(
        db_session,
        job="email.delivery",
        status="finished",
        duration_ms=12,
        details={"sent": 1, "token": "nao-pode"},
    )
    db_session.commit()
    row = db_session.scalars(select(LogEvent).where(LogEvent.category == "job")).one()
    assert row.module == "email.delivery"
    assert row.level == "info"
    assert row.details == {"sent": 1, "status": "finished", "token": "[redacted]"}


def test_config_rejects_out_of_range_observability_values() -> None:
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        obs_settings(log_http_success_sample_rate=1.5)
    with pytest.raises(ValidationError):
        obs_settings(log_retention_days=0)
    with pytest.raises(ValidationError):
        obs_settings(log_level="TRACE")


def test_purge_respects_retention_and_keeps_audit_logs(db_session: Session) -> None:
    from scripts.purge_observability import purge

    now = datetime(2026, 11, 25, 12, 0, tzinfo=UTC)
    old_log = add_log(db_session, occurred_at=now - timedelta(days=31), message="log antigo")
    new_log = add_log(db_session, occurred_at=now - timedelta(days=1), message="log novo")
    old_security = SecurityEvent(
        event_type="otp.verification_failed",
        created_at=now - timedelta(days=181),
    )
    old_audit = AuditLog(
        action="admin.old",
        resource_type="test",
        created_at=now - timedelta(days=400),
    )
    db_session.add_all([old_security, old_audit])
    db_session.commit()
    old_log_id = old_log.id
    new_log_id = new_log.id
    old_security_id = old_security.id
    old_audit_id = old_audit.id

    log_count, security_count = purge(
        db_session,
        log_retention_days=30,
        security_retention_days=180,
        dry_run=False,
        now=now,
    )
    assert (log_count, security_count) == (1, 1)
    assert db_session.get(LogEvent, old_log_id) is None
    assert db_session.get(LogEvent, new_log_id) is not None
    assert db_session.get(SecurityEvent, old_security_id) is None
    assert db_session.get(AuditLog, old_audit_id) is not None
    job = db_session.scalars(select(LogEvent).where(LogEvent.module == "observability.purge")).one()
    assert job.details is not None
    assert job.details["log_events_deleted"] == 1


def test_log_security_and_audit_fill_request_context(db_session: Session) -> None:
    from app.core.request_context import bind_request_context, reset_request_context
    from app.modules.identity.audit import record_audit
    from app.modules.observability.service import log_security

    tokens = bind_request_context(
        request_id="req-123",
        correlation_id="corr-1",
        ip=IP,
        ip_hash="hash-ip",
        user_agent="agent",
        endpoint="/api/v1/x",
        method="POST",
    )
    try:
        log_security(db_session, "otp.verification_failed", user_id=None)
        record_audit(
            db_session,
            actor_user_id=None,
            action="admin.test",
            resource_type="test",
            resource_id=None,
            details={"token": "segredo"},
        )
        db_session.commit()
    finally:
        reset_request_context(tokens)

    security = db_session.scalars(select(SecurityEvent)).one()
    assert security.request_id == "req-123"
    assert security.ip == IP
    assert security.endpoint == "/api/v1/x"
    assert security.result == "failure"

    audit = db_session.scalars(select(AuditLog)).one()
    assert audit.request_id == "req-123"
    assert audit.ip == IP
    assert audit.result == "success"
    assert audit.details == {"token": "[redacted]"}


# -- endpoints administrativos -------------------------------------------
@pytest.fixture
def admin_host(db_session: Session) -> Iterator[tuple[TestClient, uuid.UUID]]:
    admin_id = make_user(db_session)
    settings = obs_settings(platform_admins=str(admin_id))
    with build_client(db_session, settings) as client:
        client.app.state.observability = MemoryDispatcher(
            obs_settings(log_http_success_sample_rate=1.0)
        )
        yield client, admin_id


def test_admin_observability_denies_non_admin(db_session: Session) -> None:
    operator_id = make_user(db_session)
    with build_client(db_session, obs_settings(platform_admins="")) as client:
        assert client.get("/api/v1/admin/observability/summary").status_code == 401
        response = client.get(
            "/api/v1/admin/observability/summary",
            headers=admin_headers(db_session, operator_id),
        )
    assert response.status_code == 403


def test_moderator_is_not_platform_admin_and_cannot_query_observability(
    db_session: Session,
) -> None:
    moderator_id = make_user(db_session)
    db_session.add(
        ModerationOperator(
            user_id=moderator_id,
            role="MODERATOR",
            active=True,
        )
    )
    db_session.commit()

    settings = obs_settings(platform_admins="", moderation_admin_user_ids="")
    with build_client(db_session, settings) as client:
        client.app.state.observability = MemoryDispatcher(
            obs_settings(log_http_success_sample_rate=1.0)
        )
        headers = admin_headers(db_session, moderator_id)

        # Confirma que a conta realmente tem o papel de moderação.
        queue = client.get("/api/v1/moderation/queue", headers=headers)
        assert queue.status_code == 200, queue.text

        target = make_user(db_session)
        routes = (
            "/api/v1/admin/observability/summary",
            "/api/v1/admin/observability/events",
            f"/api/v1/admin/observability/users/{target}/activity",
            "/api/v1/admin/observability/ips/203.0.113.10",
            "/api/v1/admin/observability/export?format=csv",
        )
        for route in routes:
            response = client.get(route, headers=headers)
            assert response.status_code == 403, (route, response.text)
            assert response.json() == {"detail": {"code": "forbidden"}}

    audits = db_session.scalars(
        select(AuditLog).where(AuditLog.action.like("observability.%"))
    ).all()
    assert audits == []


def test_events_filters_masking_and_cursor(
    db_session: Session, admin_host: tuple[TestClient, uuid.UUID]
) -> None:
    client, admin_id = admin_host
    headers = admin_headers(db_session, admin_id)
    user_id = make_user(db_session)
    base = datetime(2026, 11, 24, 12, 0, tzinfo=UTC)
    for index in range(3):
        add_log(
            db_session,
            occurred_at=base + timedelta(minutes=index),
            message=f"http {index}",
            user_id=user_id,
            request_id=f"req-{index}",
        )
    add_log(
        db_session,
        occurred_at=base + timedelta(minutes=10),
        category="job",
        level="error",
        message="job falhou",
        status=None,
        ip=None,
    )

    first = client.get(
        "/api/v1/admin/observability/events",
        headers=headers,
        params={"limit": 2},
    )
    assert first.status_code == 200, first.text
    payload = first.json()
    assert len(payload["events"]) == 2
    assert payload["next_cursor"]
    assert payload["events"][1]["ip"] == "203.0.113.•"
    assert payload["events"][1]["ip_masked"] is True

    second = client.get(
        "/api/v1/admin/observability/events",
        headers=headers,
        params={"limit": 2, "cursor": payload["next_cursor"]},
    )
    assert second.status_code == 200
    assert len(second.json()["events"]) == 2
    assert second.json()["next_cursor"] is None

    filtered = client.get(
        "/api/v1/admin/observability/events",
        headers=headers,
        params={"level": "error", "category": "job"},
    )
    body = filtered.json()
    assert [event["message"] for event in body["events"]] == ["job falhou"]
    assert body["events"][0]["ip"] is None

    by_user = client.get(
        "/api/v1/admin/observability/events",
        headers=headers,
        params={"user_id": str(user_id)},
    )
    assert {event["user_id"] for event in by_user.json()["events"]} == {str(user_id)}

    search = client.get(
        "/api/v1/admin/observability/events",
        headers=headers,
        params={"q": "http 1"},
    )
    assert [event["message"] for event in search.json()["events"]] == ["http 1"]

    invalid = client.get(
        "/api/v1/admin/observability/events",
        headers=headers,
        params={"level": "critico"},
    )
    assert invalid.status_code == 400

    audit_actions = set(
        db_session.scalars(select(AuditLog.action).where(AuditLog.action == "observability.query"))
    )
    assert audit_actions == {"observability.query"}


def test_events_can_query_canonical_trails_and_ip(
    db_session: Session, admin_host: tuple[TestClient, uuid.UUID]
) -> None:
    client, admin_id = admin_host
    headers = admin_headers(db_session, admin_id)
    base = datetime(2026, 11, 24, 12, 0, tzinfo=UTC)
    db_session.add(
        SecurityEvent(
            event_type="email.login_failed",
            result="failure",
            ip=IP,
            request_id="req-sec",
            created_at=base,
        )
    )
    db_session.add(
        AuditLog(
            action="admin.test",
            resource_type="test",
            ip=IP,
            request_id="req-audit",
            created_at=base + timedelta(minutes=1),
        )
    )
    add_log(
        db_session,
        occurred_at=base + timedelta(minutes=2),
        ip=IP,
        request_id="req-log",
        message="http com ip",
    )
    db_session.commit()

    security = client.get(
        "/api/v1/admin/observability/events",
        headers=headers,
        params={"category": "security", "level": "warn", "ip": IP},
    )
    assert security.status_code == 200, security.text
    events = security.json()["events"]
    assert len(events) == 1
    assert events[0]["source"] == "security_events"
    assert events[0]["message"] == "email.login_failed"
    assert events[0]["ip"] == "203.0.113.•"
    assert events[0]["ip_masked"] is True

    audit = client.get(
        "/api/v1/admin/observability/events",
        headers=headers,
        params={"category": "audit", "request_id": "req-audit"},
    )
    assert audit.status_code == 200
    assert [event["source"] for event in audit.json()["events"]] == ["audit_logs"]

    by_ip = client.get(
        "/api/v1/admin/observability/events",
        headers=headers,
        params={"ip": IP, "status": 200},
    )
    assert by_ip.status_code == 200
    assert [event["request_id"] for event in by_ip.json()["events"]] == ["req-log"]

    by_period = client.get(
        "/api/v1/admin/observability/events",
        headers=headers,
        params={
            "from": base.isoformat(),
            "to": (base + timedelta(minutes=3)).isoformat(),
        },
    )
    assert by_period.status_code == 200
    assert len(by_period.json()["events"]) == 1

    invalid_ip = client.get(
        "/api/v1/admin/observability/events",
        headers=headers,
        params={"ip": "nao-e-ip"},
    )
    assert invalid_ip.status_code == 400

    audit_entries = db_session.scalars(
        select(AuditLog).where(AuditLog.action == "observability.query")
    ).all()
    ip_audit = [
        entry
        for entry in audit_entries
        if entry.details and entry.details["filters"].get("has_ip_filter")
    ]
    assert ip_audit
    assert ip_audit[-1].details is not None
    assert ip_audit[-1].details["filters"]["ip"] == IP


def test_event_detail_returns_full_ip_and_audits(
    db_session: Session, admin_host: tuple[TestClient, uuid.UUID]
) -> None:
    client, admin_id = admin_host
    headers = admin_headers(db_session, admin_id)
    event = add_log(
        db_session,
        occurred_at=datetime(2026, 11, 24, 12, 0, tzinfo=UTC),
        message="erro interno",
        level="error",
        stack="Traceback ... password=segredo",
    )
    response = client.get(f"/api/v1/admin/observability/events/{event.id}", headers=headers)
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["ip"] == IP
    assert payload["ip_masked"] is False
    assert payload["stack"] == "Traceback ... password=segredo"

    missing = client.get(f"/api/v1/admin/observability/events/{uuid.uuid4()}", headers=headers)
    assert missing.status_code == 404
    assert db_session.scalars(
        select(AuditLog).where(AuditLog.action == "observability.query")
    ).all()


def test_user_activity_merges_canonical_trails(
    db_session: Session, admin_host: tuple[TestClient, uuid.UUID]
) -> None:
    client, admin_id = admin_host
    headers = admin_headers(db_session, admin_id)
    user_id = make_user(db_session)
    base = datetime(2026, 11, 24, 12, 0, tzinfo=UTC)
    add_log(db_session, occurred_at=base, user_id=user_id, message="http")
    db_session.add(
        SecurityEvent(
            user_id=user_id,
            event_type="email.login_failed",
            result="failure",
            ip=IP,
            created_at=base + timedelta(minutes=1),
        )
    )
    db_session.add(
        AuditLog(
            actor_user_id=user_id,
            action="admin.test",
            resource_type="test",
            created_at=base + timedelta(minutes=2),
        )
    )
    db_session.commit()

    response = client.get(f"/api/v1/admin/observability/users/{user_id}/activity", headers=headers)
    assert response.status_code == 200, response.text
    events = response.json()["events"]
    assert [event["source"] for event in events] == [
        "audit_logs",
        "security_events",
        "log_events",
    ]
    assert all(event["ip"] in (None, "203.0.113.•") for event in events)


def test_ip_report_full_ip_users_and_failed_logins(
    db_session: Session, admin_host: tuple[TestClient, uuid.UUID]
) -> None:
    client, admin_id = admin_host
    headers = admin_headers(db_session, admin_id)
    user_id = make_user(db_session)
    base = datetime(2026, 11, 24, 12, 0, tzinfo=UTC)
    add_log(db_session, occurred_at=base, user_id=user_id, message="a")
    add_log(db_session, occurred_at=base + timedelta(minutes=1), message="b")
    db_session.add(
        SecurityEvent(
            user_id=user_id,
            event_type="email.login_failed",
            result="failure",
            ip=IP,
            created_at=base + timedelta(minutes=2),
        )
    )
    db_session.commit()

    response = client.get(f"/api/v1/admin/observability/ips/{IP}", headers=headers)
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["ip"] == IP
    assert payload["total_events"] == 2
    assert payload["security_events"] == 1
    assert payload["failed_logins"] == 1
    assert payload["users"][0]["user_id"] == str(user_id)
    assert {event["ip"] for event in payload["events"]} == {IP}

    invalid = client.get("/api/v1/admin/observability/ips/nao-e-ip", headers=headers)
    assert invalid.status_code == 400

    audit = db_session.scalars(
        select(AuditLog).where(AuditLog.action == "observability.query")
    ).all()
    assert any(
        entry.details and entry.details.get("filters", {}).get("has_ip_filter") for entry in audit
    )


def test_summary_compares_previous_window(
    db_session: Session, admin_host: tuple[TestClient, uuid.UUID]
) -> None:
    client, admin_id = admin_host
    headers = admin_headers(db_session, admin_id)
    now = datetime.now(UTC)
    add_log(
        db_session,
        occurred_at=now - timedelta(minutes=5),
        status=500,
        level="error",
        message="erro",
    )
    add_log(
        db_session,
        occurred_at=now - timedelta(hours=30),
        status=200,
        level="info",
        message="antigo",
    )
    response = client.get(
        "/api/v1/admin/observability/summary",
        headers=headers,
        params={"window": "24h"},
    )
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["current"]["http"]["status_5xx"] == 1
    assert payload["previous"]["total_events"] == 1
    assert payload["current"]["by_level"][0]["level"] == "error"

    invalid = client.get(
        "/api/v1/admin/observability/summary",
        headers=headers,
        params={"window": "30d"},
    )
    assert invalid.status_code == 400


def test_export_is_limited_and_audited(
    db_session: Session,
) -> None:
    admin_id = make_user(db_session)
    settings = obs_settings(platform_admins=str(admin_id))
    settings.log_max_export_rows = 2
    with build_client(db_session, settings) as client:
        client.app.state.observability = MemoryDispatcher(
            obs_settings(log_http_success_sample_rate=0.0)
        )
        headers = admin_headers(db_session, admin_id)
        base = datetime(2026, 11, 24, 12, 0, tzinfo=UTC)
        for index in range(3):
            add_log(
                db_session,
                occurred_at=base + timedelta(minutes=index),
                message=f"linha {index}",
            )
        response = client.get(
            "/api/v1/admin/observability/export",
            headers=headers,
            params={"format": "csv"},
        )
        assert response.status_code == 200, response.text
        assert response.headers["X-Export-Rows"] == "2"
        assert response.headers["X-Export-Truncated"] == "true"
        lines = response.text.strip().splitlines()
        assert len(lines) == 3  # cabeçalho + 2 linhas
        assert lines[0].startswith("id,occurred_at,level,category")

        as_json = client.get(
            "/api/v1/admin/observability/export",
            headers=headers,
            params={"format": "json", "full_ip": "true"},
        )
        assert as_json.status_code == 200
        payload = json.loads(as_json.text)
        assert len(payload) == 2
        assert {row["ip"] for row in payload} == {IP}

    audit = db_session.scalars(
        select(AuditLog).where(AuditLog.action == "observability.export")
    ).all()
    assert len(audit) == 2
    assert all(entry.details and entry.details["count"] == 2 for entry in audit)


def test_admin_rate_limit_records_security_event(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.api.v1 import admin_observability

    monkeypatch.setattr(admin_observability, "ADMIN_RATE_LIMIT_PER_MINUTE", 1)
    admin_id = make_user(db_session)
    settings = obs_settings(platform_admins=str(admin_id))
    dispatcher = MemoryDispatcher(obs_settings(log_http_success_sample_rate=0.0))
    with build_client(db_session, settings) as client:
        client.app.state.observability = dispatcher
        headers = admin_headers(db_session, admin_id)
        assert client.get("/api/v1/admin/observability/events", headers=headers).status_code == 200
        limited = client.get("/api/v1/admin/observability/events", headers=headers)
    assert limited.status_code == 429
    assert limited.headers["Retry-After"]
    assert dispatcher.security[-1]["event_type"] == "http.rate_limited"
