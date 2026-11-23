"""Catálogo administrável de esportes e preço automático."""

from __future__ import annotations

from collections.abc import Iterator
from uuid import UUID

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.infrastructure.database.dependency import get_session
from app.modules.identity.models import AuditLog
from app.modules.organizations.models import Organization, OrganizationMembership
from app.modules.pricing.models import PricingBand, PricingBandTicket
from app.modules.profile.models import Sport, SportFormat
from tests.helpers_results import make_token, make_user


def api_client(
    client: TestClient, db_session: Session, *, admin_id: UUID | None = None
) -> TestClient:
    def override_session() -> Iterator[Session]:
        yield db_session

    client.app.dependency_overrides[get_session] = override_session
    settings = Settings(
        _env_file=None,
        platform_admins=str(admin_id) if admin_id is not None else "",
    )
    client.app.dependency_overrides[get_settings] = lambda: settings
    return client


def bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def sport_payload(slug: str, team_size: int = 4) -> dict[str, object]:
    return {
        "slug": slug,
        "name": slug.replace("-", " ").title(),
        "icon_key": "icon-sport-futebol-5x5",
        "sort_order": 10,
        "formats": [
            {
                "slug": f"{slug}-{team_size}x{team_size}",
                "name": f"{slug} {team_size}x{team_size}",
                "team_size": team_size,
                "duration_minutes": 60,
                "period_count": 1,
                "score_model": "sets_points",
                "positions": [],
            }
        ],
        "reason": "abertura de catálogo para teste",
    }


def admin_headers(db_session: Session) -> tuple[dict[str, str], UUID]:
    admin_id = make_user(db_session)
    return bearer(make_token(db_session, admin_id)), admin_id


def test_suggestion_uses_the_current_formula(client: TestClient, db_session: Session) -> None:
    headers, admin_id = admin_headers(db_session)
    api = api_client(client, db_session, admin_id=admin_id)

    response = api.get("/api/v1/admin/pricing/suggest?team_size=5", headers=headers)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["mode"] == "standard"
    assert len(body["bands"]) == 6
    first = body["bands"][0]
    assert first["code"] == "economica_dia"
    assert first["tickets"] == 5
    assert first["player_price_cents"] == 1550
    assert first["invariant_ok"] is True

    three = api.get("/api/v1/admin/pricing/suggest?team_size=3", headers=headers).json()
    assert three["bands"][0]["tickets"] == 8

    six = api.get("/api/v1/admin/pricing/suggest?team_size=6", headers=headers).json()
    assert six["bands"][0]["tickets"] == 4


def test_non_standard_team_size_requires_explicit_mode(
    client: TestClient, db_session: Session
) -> None:
    headers, admin_id = admin_headers(db_session)
    api = api_client(client, db_session, admin_id=admin_id)

    missing = api.get("/api/v1/admin/pricing/suggest?team_size=4", headers=headers)
    assert missing.status_code == 422
    assert missing.json() == {"detail": {"code": "pricing_mode_required"}}

    contingency = api.get(
        "/api/v1/admin/pricing/suggest?team_size=4&mode=contingency", headers=headers
    )
    assert contingency.status_code == 200, contingency.text
    assert contingency.json()["bands"][0]["tickets"] == 5

    standard = api.get("/api/v1/admin/pricing/suggest?team_size=4&mode=standard", headers=headers)
    assert standard.status_code == 200, standard.text
    assert standard.json()["bands"][0]["tickets"] == 6


def test_override_requires_reason_and_respects_the_invariant(
    client: TestClient, db_session: Session
) -> None:
    headers, admin_id = admin_headers(db_session)
    api = api_client(client, db_session, admin_id=admin_id)

    below = api.put(
        "/api/v1/admin/pricing/band-tickets",
        headers=headers,
        json={
            "band_code": "economica_dia",
            "team_size": 4,
            "tickets": 4,
            "mode": "contingency",
            "reason": "ajuste manual",
        },
    )
    assert below.status_code == 409
    assert below.json() == {"detail": {"code": "ticket_floor_violation"}}

    missing_reason = api.put(
        "/api/v1/admin/pricing/band-tickets",
        headers=headers,
        json={
            "band_code": "economica_dia",
            "team_size": 4,
            "tickets": 5,
            "mode": "contingency",
        },
    )
    assert missing_reason.status_code == 422

    stored = api.put(
        "/api/v1/admin/pricing/band-tickets",
        headers=headers,
        json={
            "band_code": "economica_dia",
            "team_size": 4,
            "tickets": 5,
            "mode": "contingency",
            "reason": "quadra 4x4 de contingência",
        },
    )
    assert stored.status_code == 200, stored.text
    assert stored.json()["tickets"] == 5
    assert stored.json()["invariant_ok"] is True

    band = db_session.scalar(select(PricingBand).where(PricingBand.code == "economica_dia"))
    row = db_session.scalar(
        select(PricingBandTicket).where(
            PricingBandTicket.band_id == band.id,
            PricingBandTicket.team_size == 4,
        )
    )
    assert row is not None and row.tickets == 5


def test_sport_is_created_inactive_and_duplicate_slug_conflicts(
    client: TestClient, db_session: Session
) -> None:
    headers, admin_id = admin_headers(db_session)
    api = api_client(client, db_session, admin_id=admin_id)

    created = api.post("/api/v1/admin/sports", headers=headers, json=sport_payload("futsal"))
    assert created.status_code == 201, created.text
    body = created.json()
    assert body["active"] is False
    assert body["formats"][0]["team_size"] == 4
    assert body["formats"][0]["players_per_team"] == 4

    duplicate = api.post("/api/v1/admin/sports", headers=headers, json=sport_payload("futsal"))
    assert duplicate.status_code == 409
    assert duplicate.json() == {"detail": {"code": "sport_slug_conflict"}}


def test_publish_requires_active_format_and_pricing(
    client: TestClient, db_session: Session
) -> None:
    headers, admin_id = admin_headers(db_session)
    api = api_client(client, db_session, admin_id=admin_id)

    created = api.post("/api/v1/admin/sports", headers=headers, json=sport_payload("futsal"))
    assert created.status_code == 201

    blocked = api.post(
        "/api/v1/admin/sports/futsal/activate",
        headers=headers,
        json={"reason": "tentativa sem preço"},
    )
    assert blocked.status_code == 409
    assert blocked.json() == {"detail": {"code": "sport_not_publishable"}}

    for band in (
        "economica_dia",
        "economica_noite",
        "padrao_dia",
        "padrao_noite",
        "coberta",
        "premium",
    ):
        response = api.put(
            "/api/v1/admin/pricing/band-tickets",
            headers=headers,
            json={
                "band_code": band,
                "team_size": 4,
                "tickets": 20,
                "mode": "contingency",
                "reason": "configuração do 4x4",
            },
        )
        assert response.status_code == 200, response.text

    activated = api.post(
        "/api/v1/admin/sports/futsal/activate",
        headers=headers,
        json={"reason": "catálogo completo"},
    )
    assert activated.status_code == 200, activated.text
    assert activated.json()["active"] is True

    public = api.get("/api/v1/catalog/sports")
    assert public.status_code == 200
    assert [item["slug"] for item in public.json()["sports"]] == ["futsal"]


def test_deactivation_preserves_formats_and_hides_public_catalog(
    client: TestClient, db_session: Session
) -> None:
    headers, admin_id = admin_headers(db_session)
    api = api_client(client, db_session, admin_id=admin_id)
    api.post("/api/v1/admin/sports", headers=headers, json=sport_payload("futsal"))
    for band in (
        "economica_dia",
        "economica_noite",
        "padrao_dia",
        "padrao_noite",
        "coberta",
        "premium",
    ):
        api.put(
            "/api/v1/admin/pricing/band-tickets",
            headers=headers,
            json={
                "band_code": band,
                "team_size": 4,
                "tickets": 20,
                "mode": "contingency",
                "reason": "configuração do 4x4",
            },
        )
    api.post(
        "/api/v1/admin/sports/futsal/activate",
        headers=headers,
        json={"reason": "catálogo completo"},
    )

    deactivated = api.post(
        "/api/v1/admin/sports/futsal/deactivate",
        headers=headers,
        json={"reason": "suspensão temporária"},
    )
    assert deactivated.status_code == 200, deactivated.text
    assert deactivated.json()["active"] is False
    assert len(deactivated.json()["formats"]) == 1

    public = api.get("/api/v1/catalog/sports")
    assert public.status_code == 200
    assert public.json()["sports"] == []

    stored = db_session.scalar(select(SportFormat).where(SportFormat.slug == "futsal-4x4"))
    assert stored is not None and stored.active is True


def test_organization_owner_and_operator_are_forbidden(
    client: TestClient, db_session: Session
) -> None:
    api = api_client(client, db_session)
    organization = Organization(name="Arena Teste")
    owner_id = make_user(db_session)
    operator_id = make_user(db_session)
    db_session.add(organization)
    db_session.flush()
    db_session.add_all(
        [
            OrganizationMembership(
                organization_id=organization.id,
                user_id=owner_id,
                role="OWNER",
            ),
            OrganizationMembership(
                organization_id=organization.id,
                user_id=operator_id,
                role="OPERATOR",
            ),
        ]
    )
    db_session.commit()

    for user_id in (owner_id, operator_id):
        response = api.get(
            "/api/v1/admin/sports",
            headers=bearer(make_token(db_session, user_id)),
        )
        assert response.status_code == 403
        assert response.json() == {"detail": {"code": "forbidden"}}


def test_admin_sports_requires_authentication(client: TestClient) -> None:
    assert client.get("/api/v1/admin/sports").status_code == 401


def test_admin_reason_is_trimmed_and_required(client: TestClient, db_session: Session) -> None:
    headers, admin_id = admin_headers(db_session)
    api = api_client(client, db_session, admin_id=admin_id)

    blank = api.post(
        "/api/v1/admin/sports",
        headers=headers,
        json={**sport_payload("futsal"), "reason": "   "},
    )
    assert blank.status_code == 422
    assert blank.json() == {"detail": {"code": "reason_required"}}


def test_inactive_sport_and_format_never_reach_public_catalog(
    client: TestClient, db_session: Session
) -> None:
    api = api_client(client, db_session)
    sport = Sport(
        slug="futevolei",
        name="Futevôlei",
        icon_key="icon-sport-futevolei-3x3",
        sort_order=30,
        active=False,
    )
    db_session.add(sport)
    db_session.flush()
    db_session.add(
        SportFormat(
            sport_id=sport.id,
            slug="futevolei-3x3",
            name="Futevôlei 3x3",
            team_size=3,
            players_per_team=3,
            total_participants=6,
            play_minutes=45,
            break_minutes=0,
            duration_minutes=45,
            period_count=1,
            score_model="sets_points",
            positions=[],
            version=1,
            active=True,
        )
    )
    db_session.commit()

    catalog = api.get("/api/v1/catalog/sports").json()["sports"]
    assert all(item["slug"] != "futevolei" for item in catalog)


def test_sport_category_defaults_to_collective_and_can_be_changed(
    client: TestClient, db_session: Session
) -> None:
    headers, admin_id = admin_headers(db_session)
    api = api_client(client, db_session, admin_id=admin_id)

    created = api.post("/api/v1/admin/sports", headers=headers, json=sport_payload("futsal"))
    assert created.status_code == 201, created.text
    assert created.json()["category"] == "collective"

    stored = db_session.scalar(select(Sport).where(Sport.slug == "futsal"))
    assert stored is not None and stored.category == "collective"

    updated = api.patch(
        "/api/v1/admin/sports/futsal",
        headers=headers,
        json={"category": "racket", "reason": "reclassificacao do catalogo"},
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["category"] == "racket"
    assert stored.category == "racket"

    listed = api.get("/api/v1/admin/sports", headers=headers)
    assert listed.status_code == 200
    assert listed.json()["sports"][0]["category"] == "racket"

    audit = db_session.scalar(
        select(AuditLog)
        .where(AuditLog.action == "admin.sport.update")
        .order_by(AuditLog.created_at.desc())
    )
    assert audit is not None
    assert audit.details is not None
    assert audit.details["category"] == "racket"


def test_sport_category_accepts_explicit_value_on_create(
    client: TestClient, db_session: Session
) -> None:
    headers, admin_id = admin_headers(db_session)
    api = api_client(client, db_session, admin_id=admin_id)

    payload = {**sport_payload("corrida"), "category": "individual"}
    created = api.post("/api/v1/admin/sports", headers=headers, json=payload)
    assert created.status_code == 201, created.text
    assert created.json()["category"] == "individual"

    audit = db_session.scalar(
        select(AuditLog)
        .where(AuditLog.action == "admin.sport.create")
        .order_by(AuditLog.created_at.desc())
    )
    assert audit is not None
    assert audit.details is not None
    assert audit.details["category"] == "individual"


def test_sport_category_rejects_unknown_values(client: TestClient, db_session: Session) -> None:
    headers, admin_id = admin_headers(db_session)
    api = api_client(client, db_session, admin_id=admin_id)

    invalid_create = api.post(
        "/api/v1/admin/sports",
        headers=headers,
        json={**sport_payload("futsal"), "category": "mixed"},
    )
    assert invalid_create.status_code == 422

    api.post("/api/v1/admin/sports", headers=headers, json=sport_payload("futsal"))
    invalid_update = api.patch(
        "/api/v1/admin/sports/futsal",
        headers=headers,
        json={"category": "mixed", "reason": "valor invalido"},
    )
    assert invalid_update.status_code == 422

    stored = db_session.scalar(select(Sport).where(Sport.slug == "futsal"))
    assert stored is not None and stored.category == "collective"
