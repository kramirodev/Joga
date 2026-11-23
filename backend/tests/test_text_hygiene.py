"""Higiene de texto de entrada: NUL/controle/bidi e curingas de filtro.

Cobre o helper compartilhado, os endpoints de texto livre e os filtros
``q``/``city`` que antes interpretavam ``%`` e ``_`` do usuário como curingas.
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from io import BytesIO
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from PIL import Image
from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.api.v1 import (
    admin_venues,
    bookings,
    chat,
    clans,
    moderation,
    organizations,
    payments,
    substitutions,
    venues,
)
from app.api.v1 import profile as profile_api
from app.core.config import Settings, get_settings
from app.core.text import (
    UnsafeText,
    escape_like,
    normalize_newlines,
    reject_control_characters,
    reject_multiline_characters,
)
from app.infrastructure.database.dependency import get_session
from app.modules.profile.models import SportFormat, UserProfile
from app.modules.venues.models import VenueSport
from app.modules.venues.storage import LocalPhotoStorage, get_photo_storage
from tests.cnpj_helpers import (
    PARTNER_CPF,
    FakeCnpjLookup,
    api_with_lookup,
    make_cnpj_user,
)
from tests.helpers_results import build_match, make_token, make_user
from tests.test_ticket_settlement import bearer, setup_context

NUL = "\x00"
BIDI = "\u202e"
BIDI_ISOLATE = "\u2066"
ZERO_WIDTH = "\u200b"


def api_client(client: TestClient, db_session: Session) -> TestClient:
    return api_with_lookup(client, db_session, FakeCnpjLookup())


def image_bytes() -> bytes:
    output = BytesIO()
    Image.new("RGB", (320, 240), (30, 120, 210)).save(output, format="PNG")
    return output.getvalue()


# -- helper compartilhado ----------------------------------------------------


@pytest.mark.parametrize("char", ["\x00", "\x01", "\x1f", "\x7f", "\r", "\n", "\t"])
def test_rejects_control_characters(char: str) -> None:
    with pytest.raises(UnsafeText):
        reject_control_characters(f"a{char}b")


def test_keeps_accents_and_emoji() -> None:
    assert reject_control_characters("João 🎾 Ñandu") == "João 🎾 Ñandu"


def test_multiline_accepts_newline_and_normalizes_crlf() -> None:
    assert normalize_newlines("linha1\r\nlinha2\rlinha3") == "linha1\nlinha2\nlinha3"
    assert reject_multiline_characters("linha1\nlinha2") == "linha1\nlinha2"


@pytest.mark.parametrize("char", ["\x00", "\x01", "\x0b", "\x1f", "\x7f", "\t"])
def test_multiline_rejects_other_controls(char: str) -> None:
    with pytest.raises(UnsafeText):
        reject_multiline_characters(f"a{char}b")


def test_multiline_rejects_bidi_and_zero_width() -> None:
    with pytest.raises(UnsafeText):
        reject_multiline_characters(f"a{BIDI}b")
    with pytest.raises(UnsafeText):
        reject_multiline_characters(f"a{ZERO_WIDTH}b")


def test_escape_like_treats_wildcards_literally() -> None:
    assert escape_like("100%_a\\b") == "100\\%\\_a\\\\b"
    assert escape_like("Arena") == "Arena"


# -- perfil ------------------------------------------------------------------


def test_profile_rejects_unsafe_text_and_keeps_unicode(
    client: TestClient,
    db_session: Session,
) -> None:
    api = api_client(client, db_session)
    user_id = make_user(db_session)
    token = make_token(db_session, user_id)
    headers = bearer(token)

    for field, value in (
        ("display_name", f"Ad{NUL}min"),
        ("bio", f"bio{NUL}"),
        ("display_name", "Ad\r\nmin"),
        ("display_name", "Ad\nmin"),
        ("display_name", f"Ad{BIDI}min"),
        ("display_name", f"Ad{BIDI_ISOLATE}min"),
        ("display_name", f"Ad{ZERO_WIDTH}min"),
    ):
        response = api.put("/api/v1/me/profile", headers=headers, json={field: value})
        assert response.status_code == 422, response.text
        assert response.json()["detail"]["code"] == "validation_error"

    multiline = api.put(
        "/api/v1/me/profile",
        headers=headers,
        json={"bio": "linha1\nlinha2"},
    )
    assert multiline.status_code == 200, multiline.text
    assert multiline.json()["bio"] == "linha1\nlinha2"
    stored = db_session.get(UserProfile, user_id)
    assert stored is not None
    assert stored.bio == "linha1\nlinha2"

    normalized = api.put(
        "/api/v1/me/profile",
        headers=headers,
        json={"bio": "linha1\r\nlinha2\rlinha3"},
    )
    assert normalized.status_code == 200, normalized.text
    assert normalized.json()["bio"] == "linha1\nlinha2\nlinha3"

    accepted = api.put(
        "/api/v1/me/profile",
        headers=headers,
        json={"display_name": "João 🎾", "bio": "Amo vôlei de areia 🏐\nSempre"},
    )
    assert accepted.status_code == 200, accepted.text
    assert accepted.json()["display_name"] == "JOÃO 🎾"
    assert accepted.json()["bio"] == "Amo vôlei de areia 🏐\nSempre"


# -- chat --------------------------------------------------------------------


def test_chat_multiline_and_control_policy(client: TestClient, db_session: Session) -> None:
    api = api_client(client, db_session)
    match, users, _, _ = build_match(db_session, checked_in=10)
    token = make_token(db_session, users[0])

    for index, body in enumerate((f"bom jogo{NUL}", "bom jogo\x0b")):
        rejected = api.post(
            f"/api/v1/lobbies/{match.lobby_id}/messages",
            headers={**bearer(token), "Idempotency-Key": f"hygiene-chat-bad-{index}"},
            json={"body": body},
        )
        assert rejected.status_code == 422, rejected.text
        assert rejected.json()["detail"]["code"] == "validation_error"

    accepted = api.post(
        f"/api/v1/lobbies/{match.lobby_id}/messages",
        headers={**bearer(token), "Idempotency-Key": "hygiene-chat-ok"},
        json={"body": "bom jogo 🎾\nsegunda linha"},
    )
    assert accepted.status_code == 201, accepted.text
    assert accepted.json()["body"] == "bom jogo 🎾\nsegunda linha"

    normalized = api.post(
        f"/api/v1/lobbies/{match.lobby_id}/messages",
        headers={**bearer(token), "Idempotency-Key": "hygiene-chat-crlf"},
        json={"body": "linha1\r\nlinha2"},
    )
    assert normalized.status_code == 201, normalized.text
    assert normalized.json()["body"] == "linha1\nlinha2"


# -- clãs --------------------------------------------------------------------


def test_clan_rejects_nul_and_filters_literal_wildcards(
    client: TestClient,
    db_session: Session,
) -> None:
    api = api_client(client, db_session)
    user_id = make_user(db_session)
    token = make_token(db_session, user_id)
    headers = bearer(token)

    for payload in (
        {"name": f"Cla{NUL}", "tag": "CLN"},
        {"name": "Clã Teste", "tag": f"C{NUL}"},
        {"name": "Clã Teste", "tag": "CLT", "description": f"desc{NUL}"},
    ):
        rejected = api.post("/api/v1/clans", headers=headers, json=payload)
        assert rejected.status_code == 422, rejected.text

    created = api.post(
        "/api/v1/clans",
        headers=headers,
        json={"name": "Clã Tijuca 🏐", "tag": "TFC", "description": "Treino de vôlei"},
    )
    assert created.status_code == 201, created.text

    everything = api.get("/api/v1/clans", headers=headers, params={"q": "%"})
    assert everything.status_code == 200, everything.text
    assert everything.json()["clans"] == []

    literal_suffix = api.get("/api/v1/clans", headers=headers, params={"q": "Tijuca%"})
    assert literal_suffix.status_code == 200
    assert literal_suffix.json()["clans"] == []

    substring = api.get("/api/v1/clans", headers=headers, params={"q": "tijuca"})
    assert substring.status_code == 200
    assert [item["id"] for item in substring.json()["clans"]] == [created.json()["id"]]

    join = api.post(
        f"/api/v1/clans/{created.json()['id']}/join",
        headers=headers,
        json={"message": f"quero entrar{NUL}"},
    )
    assert join.status_code == 422, join.text
    assert join.json()["detail"]["code"] == "validation_error"


# -- organizações e quadras --------------------------------------------------


def test_organization_and_venue_reject_nul(
    client: TestClient,
    db_session: Session,
) -> None:
    api = api_client(client, db_session)
    user_id = make_cnpj_user(db_session)
    token = make_token(db_session, user_id)
    headers = bearer(token)

    rejected_org = api.post(
        "/api/v1/organizations",
        headers=headers,
        json={"name": f"Arena{NUL}"},
    )
    assert rejected_org.status_code == 422, rejected_org.text
    assert rejected_org.json()["detail"]["code"] == "validation_error"

    created = api.post(
        "/api/v1/organizations",
        headers=headers,
        json={
            "name": "Arena Ação 🏟️",
            "cnpj": "11222333000181",
            "cpf": PARTNER_CPF,
        },
    )
    assert created.status_code == 201, created.text
    organization_id = created.json()["id"]

    base = f"/api/v1/organizations/{organization_id}/venues"
    for field, value in (
        ("name", f"Quadra{NUL}"),
        ("city", f"Rio{NUL}"),
        ("address_line", f"Rua A{NUL}"),
    ):
        payload = {
            "name": "Arena Centro",
            "city": "Rio de Janeiro",
            "state": "RJ",
            "latitude": -22.9,
            "longitude": -43.2,
        }
        payload[field] = value
        rejected = api.post(base, headers=headers, json=payload)
        assert rejected.status_code == 422, rejected.text
        assert rejected.json()["detail"]["code"] == "validation_error"

    venue = api.post(
        base,
        headers=headers,
        json={
            "name": "Arena Centro 🏟️",
            "city": "Rio de Janeiro",
            "state": "RJ",
            "address_line": "Av. Atlântica, 100",
            "latitude": -22.9,
            "longitude": -43.2,
        },
    )
    assert venue.status_code == 201, venue.text


def test_space_and_photo_caption_reject_nul(
    client: TestClient,
    db_session: Session,
    tmp_path: Path,
) -> None:
    storage = LocalPhotoStorage(tmp_path)
    api = api_client(client, db_session)
    client.app.dependency_overrides[get_photo_storage] = lambda: storage
    user_id = make_cnpj_user(db_session)
    token = make_token(db_session, user_id)
    headers = bearer(token)

    organization = api.post(
        "/api/v1/organizations",
        headers=headers,
        json={
            "name": "Arena Mídia",
            "cnpj": "11222333000181",
            "cpf": PARTNER_CPF,
        },
    )
    assert organization.status_code == 201, organization.text
    venue = api.post(
        f"/api/v1/organizations/{organization.json()['id']}/venues",
        headers=headers,
        json={
            "name": "Arena Mídia Centro",
            "city": "Rio de Janeiro",
            "state": "RJ",
            "latitude": -22.9,
            "longitude": -43.2,
        },
    )
    assert venue.status_code == 201, venue.text
    base = f"/api/v1/organizations/{organization.json()['id']}/venues/{venue.json()['id']}"

    for payload in (
        {"name": f"Quadra{NUL}"},
        {"name": "Quadra 1", "description": f"Coberta{NUL}"},
    ):
        rejected = api.post(f"{base}/spaces", headers=headers, json=payload)
        assert rejected.status_code == 422, rejected.text
        assert rejected.json()["detail"]["code"] == "validation_error"

    space = api.post(
        f"{base}/spaces",
        headers=headers,
        json={"name": "Quadra Ação", "description": "Coberta e iluminada"},
    )
    assert space.status_code == 201, space.text

    rejected_photo = api.post(
        f"{base}/photos",
        headers=headers,
        files={"file": ("quadra.png", image_bytes(), "image/png")},
        data={"caption": f"Quadra{NUL}", "space_id": space.json()["id"]},
    )
    assert rejected_photo.status_code == 422, rejected_photo.text
    assert rejected_photo.json()["detail"]["code"] == "invalid_input"

    accepted_photo = api.post(
        f"{base}/photos",
        headers=headers,
        files={"file": ("quadra.png", image_bytes(), "image/png")},
        data={"caption": "Quadra coberta 🏐"},
    )
    assert accepted_photo.status_code == 201, accepted_photo.text
    assert accepted_photo.json()["caption"] == "Quadra coberta 🏐"


# -- reservas ----------------------------------------------------------------


def test_booking_cancel_rejects_nul_reason(
    client: TestClient,
    db_session: Session,
) -> None:
    api = api_client(client, db_session)
    user_id = make_user(db_session)
    token = make_token(db_session, user_id)

    rejected = api.post(
        f"/api/v1/bookings/{uuid4()}/cancel",
        headers=bearer(token),
        json={"reason": f"desisti{NUL}"},
    )
    assert rejected.status_code == 422, rejected.text
    assert rejected.json()["detail"]["code"] == "validation_error"


# -- administração -----------------------------------------------------------


def admin_api(
    client: TestClient,
    db_session: Session,
) -> tuple[TestClient, dict[str, str]]:
    admin_id = make_user(db_session)
    settings = Settings(
        _env_file=None,
        platform_admins=str(admin_id),
        ticket_purchase_enabled=True,
    )

    def override_session() -> Iterator[Session]:
        yield db_session

    client.app.dependency_overrides[get_session] = override_session
    client.app.dependency_overrides[get_settings] = lambda: settings
    return client, bearer(make_token(db_session, admin_id))


def test_admin_rejects_unsafe_text_and_filters_literal_wildcards(
    client: TestClient,
    db_session: Session,
) -> None:
    api, headers = admin_api(client, db_session)

    rejected_display_name = api.post(
        "/api/v1/admin/users",
        headers=headers,
        json={
            "email": "admin-hygiene@joga.example",
            "password": "SenhaSeguraBeta123",
            "display_name": f"Ad{BIDI}min",
            "reason": "cadastro operacional",
        },
    )
    assert rejected_display_name.status_code == 422, rejected_display_name.text
    assert rejected_display_name.json()["detail"]["code"] == "validation_error"

    rejected_reason = api.post(
        "/api/v1/admin/users",
        headers=headers,
        json={
            "email": "admin-hygiene@joga.example",
            "password": "SenhaSeguraBeta123",
            "reason": f"cadastro{NUL}",
        },
    )
    assert rejected_reason.status_code == 422, rejected_reason.text

    target = make_user(db_session)
    rejected_suspend = api.post(
        f"/api/v1/admin/users/{target}/suspend",
        headers=headers,
        json={"reason": f"abuso{NUL}"},
    )
    assert rejected_suspend.status_code == 422, rejected_suspend.text

    searched = make_user(db_session)
    db_session.add_all(
        [
            UserProfile(user_id=searched, display_name="Busca 100%"),
            UserProfile(user_id=make_user(db_session), display_name="Busca Comum"),
            UserProfile(user_id=make_user(db_session), display_name="Busca%Literal"),
        ]
    )
    db_session.commit()

    everything = api.get("/api/v1/admin/users", headers=headers, params={"q": "%"})
    assert everything.status_code == 200, everything.text
    # Antes do escape, "%" casava com os três perfis de busca.
    assert everything.json()["total"] == 2

    literal_suffix = api.get("/api/v1/admin/users", headers=headers, params={"q": "Busca%"})
    assert literal_suffix.status_code == 200
    # Antes do escape, "Busca%" era prefixo e casava também com os outros dois.
    assert literal_suffix.json()["total"] == 1
    assert literal_suffix.json()["users"][0]["display_name"] == "Busca%Literal"

    literal_percent = api.get("/api/v1/admin/users", headers=headers, params={"q": "100%"})
    assert literal_percent.status_code == 200
    assert literal_percent.json()["total"] == 1
    assert literal_percent.json()["users"][0]["display_name"] == "Busca 100%"


def admin_sport_payload() -> dict:
    return {
        "slug": "futsal",
        "name": "Futsal",
        "icon_key": "icon-sport-futebol-5x5",
        "sort_order": 10,
        "formats": [
            {
                "slug": "futsal-5x5",
                "name": "Futsal 5x5",
                "team_size": 5,
                "duration_minutes": 60,
                "period_count": 1,
                "score_model": "sets_points",
                "positions": [],
            }
        ],
        "reason": "abertura do catálogo",
    }


def test_admin_catalog_rejects_nul_and_accepts_seed_values(
    client: TestClient,
    db_session: Session,
) -> None:
    api, headers = admin_api(client, db_session)

    for field in ("slug", "name", "icon_key"):
        payload = admin_sport_payload()
        payload[field] = f"{payload[field]}{NUL}"
        rejected = api.post("/api/v1/admin/sports", headers=headers, json=payload)
        assert rejected.status_code == 422, rejected.text
        assert rejected.json()["detail"]["code"] == "validation_error"

    for field in ("slug", "name"):
        payload = admin_sport_payload()
        payload["formats"][0][field] = f"{payload['formats'][0][field]}{NUL}"
        rejected = api.post("/api/v1/admin/sports", headers=headers, json=payload)
        assert rejected.status_code == 422, rejected.text
        assert rejected.json()["detail"]["code"] == "validation_error"

    created = api.post("/api/v1/admin/sports", headers=headers, json=admin_sport_payload())
    assert created.status_code == 201, created.text
    assert created.json()["slug"] == "futsal"
    assert created.json()["icon_key"] == "icon-sport-futebol-5x5"

    rejected_update = api.patch(
        "/api/v1/admin/sports/futsal",
        headers=headers,
        json={"name": f"Futsal{NUL}", "reason": "ajuste de catálogo"},
    )
    assert rejected_update.status_code == 422, rejected_update.text
    assert rejected_update.json()["detail"]["code"] == "validation_error"


# -- descoberta --------------------------------------------------------------


def test_discovery_city_filter_does_not_expand_wildcards(
    client: TestClient,
    db_session: Session,
) -> None:
    api = api_client(client, db_session)
    context = setup_context(db_session)
    context["venue"].city = "Rio de Janeiro"
    format_ = db_session.get(SportFormat, context["lobby"].format_id)
    assert format_ is not None
    db_session.add(VenueSport(venue_space_id=context["space"].id, sport_id=format_.sport_id))
    db_session.commit()

    token = context["tokens"][0]
    everything = api.get(
        "/api/v1/discovery/bookable-venues",
        headers=bearer(token),
        params={"city": "%"},
    )
    assert everything.status_code == 200, everything.text
    assert everything.json()["total"] == 0

    substring = api.get(
        "/api/v1/discovery/bookable-venues",
        headers=bearer(token),
        params={"city": "janeiro"},
    )
    assert substring.status_code == 200
    assert substring.json()["total"] == 1

    literal = api.get(
        "/api/v1/discovery/bookable-venues",
        headers=bearer(token),
        params={"city": "Janeiro%"},
    )
    assert literal.status_code == 200
    assert literal.json()["total"] == 0


# -- schemas de entrada não cobertos por HTTP acima -------------------------

NOW = datetime(2026, 12, 15, 20, 0, tzinfo=UTC)

SCHEMA_CASES = [
    (
        moderation.ReportCreate,
        {
            "target_user_id": UUID(int=1),
            "lobby_id": UUID(int=2),
            "category": "SPAM",
            "description": f"denúncia{NUL}",
        },
    ),
    (moderation.AppealCreate, {"reason": f"recurso{NUL}"}),
    (
        moderation.DecisionRequest,
        {"decision": "WARN", "reason": f"motivo{NUL}"},
    ),
    (
        moderation.AppealDecisionRequest,
        {"decision": "REJECTED", "reason": f"motivo{NUL}"},
    ),
    (payments.RefundRequest, {"reason": f"estorno{NUL}"}),
    (
        payments.DisputeCreateRequest,
        {"booking_id": UUID(int=3), "reason": f"contestação{NUL}"},
    ),
    (
        payments.DisputeDecisionRequest,
        {"decision": "ACCEPTED", "reason": f"decisão{NUL}"},
    ),
    (substitutions.NoShowRequest, {"reason": f"no-show{NUL}"}),
    (
        venues.BlackoutCreate,
        {"starts_at": NOW, "ends_at": NOW + timedelta(hours=1), "reason": f"obra{NUL}"},
    ),
    (
        venues.ClosureCreate,
        {"starts_at": NOW, "ends_at": NOW + timedelta(hours=1), "reason": f"feriado{NUL}"},
    ),
    (venues.PhotoReview, {"decision": "REJECTED", "reason": f"foto{NUL}"}),
    (
        admin_venues.AdminVenueCreateRequest,
        {"name": f"Arena{NUL}", "reason": "cadastro"},
    ),
    (
        admin_venues.AdminSpaceCreateRequest,
        {
            "name": "Quadra 1",
            "sport_id": UUID(int=4),
            "format_id": UUID(int=5),
            "price_cents": 10_000,
            "reason": f"cadastro{NUL}",
        },
    ),
    (clans.JoinRequestCreate, {"message": f"oi{NUL}"}),
    (clans.DecisionRequest, {"approve": True, "note": f"nota{NUL}"}),
    (clans.MessageCreate, {"body": f"oi{NUL}"}),
    (clans.ReportCreate, {"reason": f"ofensa{NUL}"}),
    (clans.ReportDecision, {"decision": "RESTORE", "note": f"nota{NUL}"}),
    (chat.MessageRequest, {"body": f"oi{NUL}"}),
    (profile_api.ProfileUpdateRequest, {"display_name": f"Ad{BIDI}min"}),
    (profile_api.ProfileUpdateRequest, {"bio": f"bio{NUL}"}),
    (bookings.CancelRequest, {"reason": f"desisti{NUL}"}),
    (organizations.OrganizationCreate, {"name": f"Arena{NUL}"}),
    (
        organizations.VenueCreate,
        {
            "name": "Arena",
            "latitude": -22.9,
            "longitude": -43.2,
            "address_line": f"Rua{NUL}",
        },
    ),
    (venues.SpaceCreate, {"name": "Quadra", "description": f"Coberta{NUL}"}),
]


@pytest.mark.parametrize(("model", "payload"), SCHEMA_CASES)
def test_request_schemas_reject_control_characters(
    model: type,
    payload: dict,
) -> None:
    with pytest.raises(ValidationError):
        model(**payload)
