"""Edição administrativa de formatos esportivos (Parte E.4)."""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from uuid import UUID

from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.infrastructure.database.dependency import get_session
from app.modules.identity.audit import AuditLog
from app.modules.matchmaking.models import Lobby
from app.modules.organizations.models import Organization, OrganizationMembership
from app.modules.profile.models import SportFormat
from tests.helpers_results import make_token, make_user

BANDS = ("economica_dia", "economica_noite", "padrao_dia", "padrao_noite", "coberta", "premium")


def api_client(
    client: TestClient, db_session: Session, *, admin_id: UUID | None = None
) -> TestClient:
    def override_session() -> Iterator[Session]:
        yield db_session

    settings = Settings(
        _env_file=None,
        platform_admins=str(admin_id) if admin_id is not None else "",
        ticket_purchase_enabled=True,
    )
    client.app.dependency_overrides[get_session] = override_session
    client.app.dependency_overrides[get_settings] = lambda: settings
    return client


def bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def admin_setup(db_session: Session) -> tuple[UUID, dict[str, str]]:
    admin_id = make_user(db_session)
    return admin_id, bearer(make_token(db_session, admin_id))


def create_sport(api: TestClient, headers: dict[str, str], *, team_size: int = 5) -> dict:
    response = api.post(
        "/api/v1/admin/sports",
        headers=headers,
        json={
            "slug": "futsal",
            "name": "Futsal",
            "icon_key": "icon-sport-futebol-5x5",
            "sort_order": 10,
            "formats": [
                {
                    "slug": f"futsal-{team_size}x{team_size}",
                    "name": f"Futsal {team_size}x{team_size}",
                    "team_size": team_size,
                    "duration_minutes": 60,
                    "period_count": 1,
                    "score_model": "sets_points",
                    "positions": [],
                }
            ],
            "reason": "catálogo de teste",
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def configure_prices(api: TestClient, headers: dict[str, str], team_size: int) -> None:
    for band in BANDS:
        response = api.put(
            "/api/v1/admin/pricing/band-tickets",
            headers=headers,
            json={
                "band_code": band,
                "team_size": team_size,
                "tickets": 30,
                "mode": "contingency",
                "reason": "preço de teste",
            },
        )
        assert response.status_code == 200, response.text


def test_edit_format_allowed_fields_and_audit(client: TestClient, db_session: Session) -> None:
    admin_id, headers = admin_setup(db_session)
    api = api_client(client, db_session, admin_id=admin_id)
    sport = create_sport(api, headers)
    format_id = sport["formats"][0]["id"]

    updated = api.patch(
        f"/api/v1/admin/sports/futsal/formats/{format_id}",
        headers=headers,
        json={
            "name": "Futsal adulto",
            "duration_minutes": 50,
            "period_count": 2,
            "score_model": "goals",
            "positions": ["goleiro", "ala", "pivo"],
            "reason": "padronização do formato",
        },
    )
    assert updated.status_code == 200, updated.text
    body = updated.json()
    assert body["name"] == "Futsal adulto"
    assert body["duration_minutes"] == 50
    assert body["period_count"] == 2
    assert body["score_model"] == "goals"
    assert body["positions"] == ["goleiro", "ala", "pivo"]
    assert body["version"] == 2
    assert body["in_use"] is False

    audit = db_session.scalar(
        select(AuditLog).where(AuditLog.action == "admin.sport.format.update")
    )
    assert audit is not None
    assert audit.reason == "padronização do formato"
    assert audit.details is not None
    changed = audit.details["changed"]
    assert "name" in changed
    assert changed["name"] == {"before": "Futsal 5x5", "after": "Futsal adulto"}
    assert audit.details["ip_hash"]


def test_edit_team_size_without_use_and_with_configured_price(
    client: TestClient, db_session: Session
) -> None:
    admin_id, headers = admin_setup(db_session)
    api = api_client(client, db_session, admin_id=admin_id)
    sport = create_sport(api, headers)
    format_id = sport["formats"][0]["id"]

    updated = api.patch(
        f"/api/v1/admin/sports/futsal/formats/{format_id}",
        headers=headers,
        json={"team_size": 3, "reason": "redução para 3x3"},
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["team_size"] == 3
    assert updated.json()["players_per_team"] == 3
    assert updated.json()["total_participants"] == 6


def test_edit_team_size_with_use_returns_conflict(client: TestClient, db_session: Session) -> None:
    admin_id, headers = admin_setup(db_session)
    api = api_client(client, db_session, admin_id=admin_id)
    sport = create_sport(api, headers)
    format_data = sport["formats"][0]
    start = datetime(2026, 12, 1, 18, 0, tzinfo=UTC)
    db_session.add(
        Lobby(
            format_id=UUID(format_data["id"]),
            format_version=format_data["version"],
            origin="matchmaking",
            mode="casual",
            status="scheduled",
            court_preference="ANY",
            scheduled_start_at=start,
            scheduled_end_at=start + timedelta(minutes=60),
            duration_minutes=60,
            center_lat=-23.55,
            center_lng=-46.63,
            radius_km=10,
            algorithm_version="level_v1",
        )
    )
    db_session.commit()

    blocked = api.patch(
        f"/api/v1/admin/sports/futsal/formats/{format_data['id']}",
        headers=headers,
        json={"team_size": 4, "reason": "mudança indevida"},
    )
    assert blocked.status_code == 409
    assert blocked.json() == {"detail": {"code": "format_in_use"}}

    allowed = api.patch(
        f"/api/v1/admin/sports/futsal/formats/{format_data['id']}",
        headers=headers,
        json={"name": "Futsal em uso", "reason": "renomear sem quebrar histórico"},
    )
    assert allowed.status_code == 200, allowed.text
    assert allowed.json()["in_use"] is True


def test_add_format_without_price_creates_nothing(client: TestClient, db_session: Session) -> None:
    admin_id, headers = admin_setup(db_session)
    api = api_client(client, db_session, admin_id=admin_id)
    create_sport(api, headers)
    before = int(db_session.scalar(select(func.count()).select_from(SportFormat)) or 0)

    response = api.post(
        "/api/v1/admin/sports/futsal/formats",
        headers=headers,
        json={
            "slug": "futsal-4x4",
            "name": "Futsal 4x4",
            "team_size": 4,
            "duration_minutes": 60,
            "period_count": 1,
            "score_model": "goals",
            "positions": [],
            "reason": "variante 4x4",
        },
    )
    assert response.status_code == 422
    assert response.json() == {"detail": {"code": "pricing_not_configured"}}
    after = int(db_session.scalar(select(func.count()).select_from(SportFormat)) or 0)
    assert after == before


def test_add_format_with_price_appears_in_public_catalog(
    client: TestClient, db_session: Session
) -> None:
    admin_id, headers = admin_setup(db_session)
    api = api_client(client, db_session, admin_id=admin_id)
    create_sport(api, headers)
    activated = api.post(
        "/api/v1/admin/sports/futsal/activate",
        headers=headers,
        json={"reason": "publicar 5x5"},
    )
    assert activated.status_code == 200, activated.text
    configure_prices(api, headers, 4)

    created = api.post(
        "/api/v1/admin/sports/futsal/formats",
        headers=headers,
        json={
            "slug": "futsal-4x4",
            "name": "Futsal 4x4",
            "team_size": 4,
            "duration_minutes": 50,
            "period_count": 1,
            "score_model": "goals",
            "positions": ["goleiro", "fixo", "ala", "pivo"],
            "reason": "variante 4x4",
        },
    )
    assert created.status_code == 201, created.text
    assert created.json()["in_use"] is False

    public = api.get("/api/v1/catalog/sports")
    assert public.status_code == 200
    formats = public.json()["sports"][0]["formats"]
    assert {item["slug"] for item in formats} == {"futsal-5x5", "futsal-4x4"}


def test_deactivate_format_hides_public_and_preserves_row(
    client: TestClient, db_session: Session
) -> None:
    admin_id, headers = admin_setup(db_session)
    api = api_client(client, db_session, admin_id=admin_id)
    sport = create_sport(api, headers)
    format_id = sport["formats"][0]["id"]
    api.post(
        "/api/v1/admin/sports/futsal/activate",
        headers=headers,
        json={"reason": "publicar 5x5"},
    )

    deactivated = api.post(
        f"/api/v1/admin/sports/futsal/formats/{format_id}/deactivate",
        headers=headers,
        json={"reason": "substituído por 4x4"},
    )
    assert deactivated.status_code == 200, deactivated.text
    assert deactivated.json()["active"] is False
    assert deactivated.json()["version"] == 2

    public = api.get("/api/v1/catalog/sports")
    assert public.status_code == 200
    assert public.json()["sports"] == []

    stored = db_session.get(SportFormat, UUID(format_id))
    assert stored is not None
    assert stored.active is False

    admin_list = api.get("/api/v1/admin/sports", headers=headers)
    assert admin_list.status_code == 200
    formats = admin_list.json()["sports"][0]["formats"]
    assert len(formats) == 1
    assert formats[0]["active"] is False


def test_format_endpoints_require_platform_admin(client: TestClient, db_session: Session) -> None:
    admin_id, headers = admin_setup(db_session)
    api = api_client(client, db_session, admin_id=admin_id)
    sport = create_sport(api, headers)
    format_id = sport["formats"][0]["id"]

    organization = Organization(name="Arena Privada")
    db_session.add(organization)
    db_session.flush()
    owner_id = make_user(db_session)
    operator_id = make_user(db_session)
    db_session.add_all(
        [
            OrganizationMembership(organization_id=organization.id, user_id=owner_id, role="OWNER"),
            OrganizationMembership(
                organization_id=organization.id, user_id=operator_id, role="OPERATOR"
            ),
        ]
    )
    db_session.commit()

    player_api = api_client(client, db_session)
    for user_id in (owner_id, operator_id, make_user(db_session)):
        forbidden = player_api.patch(
            f"/api/v1/admin/sports/futsal/formats/{format_id}",
            headers=bearer(make_token(db_session, user_id)),
            json={"name": "Não pode", "reason": "sem permissão"},
        )
        assert forbidden.status_code == 403
        assert forbidden.json() == {"detail": {"code": "forbidden"}}
