"""Alertas simples derivados da observabilidade (Fase 3, ADR 0078)."""

from __future__ import annotations

import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.infrastructure.database.dependency import get_session
from app.main import create_app
from app.modules.identity.models import AuditLog, SecurityEvent
from app.modules.observability.models import LogEvent
from tests.helpers_results import make_token, make_user

ALERTS = "/api/v1/admin/observability/alerts"


def obs_settings(**overrides: Any) -> Settings:
    values: dict[str, Any] = {
        "_env_file": None,
        "environment": "test",
        "observability_enabled": False,
        "log_http_success_sample_rate": 0.0,
        "log_max_export_rows": 20_000,
    }
    values.update(overrides)
    return Settings(**values)


@contextmanager
def build_admin(
    db_session: Session,
    settings: Settings,
) -> Iterator[tuple[TestClient, dict[str, str]]]:
    admin_id = make_user(db_session)
    resolved = settings.model_copy(update={"platform_admins": str(admin_id)})
    app = create_app(resolved)

    def override_session() -> Iterator[Session]:
        yield db_session

    app.dependency_overrides[get_session] = override_session
    app.dependency_overrides[get_settings] = lambda: resolved
    with TestClient(app, client=("203.0.113.10", 50_000)) as client:
        yield client, {"Authorization": f"Bearer {make_token(db_session, admin_id)}"}


def add_log(
    session: Session,
    *,
    occurred_at: datetime,
    category: str,
    level: str = "error",
    status: int | None = None,
) -> LogEvent:
    event = LogEvent(
        occurred_at=occurred_at,
        level=level,
        category=category,
        module="test",
        message="evento",
        status=status,
    )
    session.add(event)
    session.commit()
    return event


def add_failed_login(session: Session, *, occurred_at: datetime) -> SecurityEvent:
    event = SecurityEvent(
        event_type="email.login_failed",
        result="failure",
        created_at=occurred_at,
    )
    session.add(event)
    session.commit()
    return event


def alert_map(payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {item["code"]: item for item in payload["alerts"]}


def test_alerts_are_empty_without_events(db_session: Session) -> None:
    with build_admin(db_session, obs_settings()) as (client, headers):
        response = client.get(ALERTS, params={"window": "24h"}, headers=headers)
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["window"] == "24h"
    assert payload["alerts"] == []
    assert payload["from_at"] < payload["to_at"]


def test_invalid_window_is_rejected(db_session: Session) -> None:
    with build_admin(db_session, obs_settings()) as (client, headers):
        response = client.get(ALERTS, params={"window": "30d"}, headers=headers)
    assert response.status_code == 400
    assert response.json() == {"detail": {"code": "invalid_window"}}


def test_login_failures_threshold(db_session: Session) -> None:
    now = datetime.now(UTC)
    settings = obs_settings(observability_alert_login_failures=2)
    with build_admin(db_session, settings) as (client, headers):
        add_failed_login(db_session, occurred_at=now - timedelta(minutes=10))
        below = client.get(ALERTS, headers=headers)
        assert below.status_code == 200, below.text
        assert "login_failures" not in alert_map(below.json())

        add_failed_login(db_session, occurred_at=now - timedelta(minutes=5))
        equal = alert_map(client.get(ALERTS, headers=headers).json())["login_failures"]
        assert equal == {
            "code": "login_failures",
            "level": "warning",
            "count": 2,
            "threshold": 2,
        }

        add_failed_login(db_session, occurred_at=now - timedelta(minutes=1))
        above = alert_map(client.get(ALERTS, headers=headers).json())["login_failures"]
        assert above["count"] == 3


def test_server_errors_threshold_is_critical(db_session: Session) -> None:
    now = datetime.now(UTC)
    settings = obs_settings(observability_alert_server_errors=2)
    with build_admin(db_session, settings) as (client, headers):
        add_log(db_session, occurred_at=now - timedelta(minutes=3), category="http", status=500)
        assert "server_errors" not in alert_map(client.get(ALERTS, headers=headers).json())

        # 4xx e 500 fora da categoria http não contam.
        add_log(db_session, occurred_at=now - timedelta(minutes=2), category="http", status=404)
        add_log(db_session, occurred_at=now - timedelta(minutes=2), category="app", status=500)
        assert "server_errors" not in alert_map(client.get(ALERTS, headers=headers).json())

        add_log(db_session, occurred_at=now - timedelta(minutes=1), category="http", status=503)
        alert = alert_map(client.get(ALERTS, headers=headers).json())["server_errors"]
    assert alert == {
        "code": "server_errors",
        "level": "critical",
        "count": 2,
        "threshold": 2,
    }


def test_failed_jobs_threshold(db_session: Session) -> None:
    now = datetime.now(UTC)
    settings = obs_settings(observability_alert_failed_jobs=1)
    with build_admin(db_session, settings) as (client, headers):
        add_log(db_session, occurred_at=now - timedelta(minutes=2), category="job", level="info")
        assert "failed_jobs" not in alert_map(client.get(ALERTS, headers=headers).json())

        add_log(db_session, occurred_at=now - timedelta(minutes=1), category="job", level="error")
        alert = alert_map(client.get(ALERTS, headers=headers).json())["failed_jobs"]
    assert alert == {
        "code": "failed_jobs",
        "level": "warning",
        "count": 1,
        "threshold": 1,
    }


def test_client_errors_threshold_includes_fatal(db_session: Session) -> None:
    now = datetime.now(UTC)
    settings = obs_settings(observability_alert_client_errors=2)
    with build_admin(db_session, settings) as (client, headers):
        add_log(db_session, occurred_at=now - timedelta(minutes=2), category="client", level="warn")
        assert "client_errors" not in alert_map(client.get(ALERTS, headers=headers).json())

        add_log(
            db_session, occurred_at=now - timedelta(minutes=2), category="client", level="error"
        )
        assert "client_errors" not in alert_map(client.get(ALERTS, headers=headers).json())

        add_log(
            db_session, occurred_at=now - timedelta(minutes=1), category="client", level="fatal"
        )
        alert = alert_map(client.get(ALERTS, headers=headers).json())["client_errors"]
    assert alert == {
        "code": "client_errors",
        "level": "warning",
        "count": 2,
        "threshold": 2,
    }


def test_alerts_are_audited(db_session: Session) -> None:
    with build_admin(db_session, obs_settings()) as (client, headers):
        response = client.get(ALERTS, params={"window": "7d"}, headers=headers)
    assert response.status_code == 200

    audit = db_session.scalars(
        select(AuditLog).where(AuditLog.action == "observability.query")
    ).all()
    assert len(audit) == 1
    assert audit[0].details is not None
    assert audit[0].details["view"] == "alerts"
    assert audit[0].details["window"] == "7d"


def test_alerts_deny_non_admin(db_session: Session) -> None:
    player_id = make_user(db_session)
    settings = obs_settings(platform_admins="")
    with build_admin(db_session, settings) as (client, _headers):
        headers = {"Authorization": f"Bearer {make_token(db_session, player_id)}"}
        response = client.get(ALERTS, headers=headers)
        anonymous = client.get(ALERTS)
    assert response.status_code == 403
    assert anonymous.status_code == 401


def test_alert_thresholds_reject_zero() -> None:
    with pytest.raises(ValidationError):
        obs_settings(observability_alert_login_failures=0)
    with pytest.raises(ValidationError):
        obs_settings(observability_alert_server_errors=0)
    with pytest.raises(ValidationError):
        obs_settings(observability_alert_failed_jobs=0)
    with pytest.raises(ValidationError):
        obs_settings(observability_alert_client_errors=0)
    with pytest.raises(ValidationError):
        obs_settings(client_events_rate_limit_per_minute=0)


def test_alerts_ignore_events_outside_window(db_session: Session) -> None:
    now = datetime.now(UTC)
    settings = obs_settings(observability_alert_server_errors=1)
    with build_admin(db_session, settings) as (client, headers):
        add_log(
            db_session,
            occurred_at=now - timedelta(days=2),
            category="http",
            status=500,
        )
        response = client.get(ALERTS, params={"window": "24h"}, headers=headers)
    assert response.status_code == 200
    assert alert_map(response.json()) == {}


def test_audit_uses_anonymous_resource_not_user(db_session: Session) -> None:
    # Auditoria de alertas não deve carregar identificadores do payload.
    with build_admin(db_session, obs_settings()) as (client, headers):
        client.get(ALERTS, headers=headers)
    audit = db_session.scalars(
        select(AuditLog).where(AuditLog.action == "observability.query")
    ).one()
    assert audit.details is not None
    assert "filters" in audit.details
    assert uuid.UUID(str(audit.actor_user_id)) is not None
