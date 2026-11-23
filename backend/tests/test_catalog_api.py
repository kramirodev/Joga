"""Catálogo público de esportes: busca por nome/slug e filtro por tipo."""

from __future__ import annotations

from collections.abc import Iterator

from fastapi.testclient import TestClient
from sqlalchemy import event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from app.infrastructure.database.dependency import get_session
from app.modules.profile.models import Sport, SportFormat


def api_client(client: TestClient, db_session: Session) -> TestClient:
    def override_session() -> Iterator[Session]:
        yield db_session

    client.app.dependency_overrides[get_session] = override_session
    return client


def add_sport(
    db_session: Session,
    *,
    slug: str,
    name: str,
    category: str,
    sort_order: int,
    active: bool = True,
    format_active: bool = True,
) -> Sport:
    sport = Sport(
        slug=slug,
        name=name,
        category=category,
        icon_key="icon-sport-futebol-5x5",
        sort_order=sort_order,
        active=active,
    )
    db_session.add(sport)
    db_session.flush()
    db_session.add(
        SportFormat(
            sport_id=sport.id,
            slug=f"{slug}-4x4",
            name=f"{name} 4x4",
            team_size=4,
            players_per_team=4,
            total_participants=8,
            play_minutes=60,
            break_minutes=0,
            duration_minutes=60,
            period_count=1,
            score_model="sets_points",
            positions=[],
            version=1,
            active=format_active,
        )
    )
    db_session.commit()
    return sport


def seed_catalog(db_session: Session) -> None:
    add_sport(
        db_session,
        slug="futebol",
        name="Futebol",
        category="collective",
        sort_order=10,
    )
    add_sport(
        db_session,
        slug="tenis",
        name="Tênis",
        category="racket",
        sort_order=20,
    )
    add_sport(
        db_session,
        slug="fute-bol-100",
        name="Fute_bol 100%",
        category="collective",
        sort_order=5,
    )
    add_sport(
        db_session,
        slug="futebol-100",
        name="Futebol 100 por cento",
        category="collective",
        sort_order=40,
    )
    add_sport(
        db_session,
        slug="padel-inativo",
        name="Padel Inativo",
        category="racket",
        sort_order=50,
        active=False,
    )
    add_sport(
        db_session,
        slug="squash-sem-formato",
        name="Squash Sem Formato",
        category="racket",
        sort_order=60,
        format_active=False,
    )


def test_catalog_without_filters_keeps_current_contract(
    client: TestClient, db_session: Session
) -> None:
    seed_catalog(db_session)
    api = api_client(client, db_session)

    response = api.get("/api/v1/catalog/sports")
    assert response.status_code == 200, response.text
    sports = response.json()["sports"]

    assert [item["slug"] for item in sports] == [
        "fute-bol-100",
        "futebol",
        "tenis",
        "futebol-100",
    ]
    assert sports[1] == {
        "id": sports[1]["id"],
        "slug": "futebol",
        "name": "Futebol",
        "category": "collective",
        "icon_key": "icon-sport-futebol-5x5",
        "sort_order": 10,
        "active": True,
        "formats": [
            {
                "id": sports[1]["formats"][0]["id"],
                "slug": "futebol-4x4",
                "name": "Futebol 4x4",
                "team_size": 4,
                "players_per_team": 4,
                "total_participants": 8,
                "duration_minutes": 60,
                "period_count": 1,
                "score_model": "sets_points",
                "positions": [],
                "active": True,
                "version": 1,
            }
        ],
    }


def test_catalog_q_is_case_insensitive_on_name_and_slug(
    client: TestClient, db_session: Session
) -> None:
    seed_catalog(db_session)
    api = api_client(client, db_session)

    by_name = api.get("/api/v1/catalog/sports", params={"q": "FUTEBOL"})
    assert by_name.status_code == 200, by_name.text
    assert [item["slug"] for item in by_name.json()["sports"]] == [
        "futebol",
        "futebol-100",
    ]

    by_slug = api.get("/api/v1/catalog/sports", params={"q": "fute-bol"})
    assert by_slug.status_code == 200, by_slug.text
    assert [item["slug"] for item in by_slug.json()["sports"]] == ["fute-bol-100"]

    accented = api.get("/api/v1/catalog/sports", params={"q": "tênis"})
    assert [item["slug"] for item in accented.json()["sports"]] == ["tenis"]


def test_catalog_q_treats_wildcards_as_literal_characters(
    client: TestClient, db_session: Session
) -> None:
    seed_catalog(db_session)
    api = api_client(client, db_session)

    underscore = api.get("/api/v1/catalog/sports", params={"q": "e_b"})
    assert underscore.status_code == 200, underscore.text
    assert [item["slug"] for item in underscore.json()["sports"]] == ["fute-bol-100"]

    percent = api.get("/api/v1/catalog/sports", params={"q": "100%"})
    assert percent.status_code == 200, percent.text
    assert [item["slug"] for item in percent.json()["sports"]] == ["fute-bol-100"]


def test_catalog_filters_by_category_and_combines_with_q(
    client: TestClient, db_session: Session
) -> None:
    seed_catalog(db_session)
    api = api_client(client, db_session)

    racket = api.get("/api/v1/catalog/sports", params={"category": "racket"})
    assert racket.status_code == 200, racket.text
    assert [item["slug"] for item in racket.json()["sports"]] == ["tenis"]

    combined = api.get("/api/v1/catalog/sports", params={"q": "futebol", "category": "racket"})
    assert combined.status_code == 200, combined.text
    assert combined.json()["sports"] == []


def test_catalog_rejects_invalid_filters(client: TestClient, db_session: Session) -> None:
    api = api_client(client, db_session)

    invalid_category = api.get("/api/v1/catalog/sports", params={"category": "mixed"})
    assert invalid_category.status_code == 422

    short_q = api.get("/api/v1/catalog/sports", params={"q": "f"})
    assert short_q.status_code == 422

    blank_q = api.get("/api/v1/catalog/sports", params={"q": "  "})
    assert blank_q.status_code == 422
    assert blank_q.json() == {"detail": {"code": "invalid_query"}}


def test_catalog_fetches_sports_and_formats_in_two_queries(
    client: TestClient, db_session: Session
) -> None:
    seed_catalog(db_session)
    api = api_client(client, db_session)
    engine = db_session.get_bind()
    assert isinstance(engine, Engine)
    statements: list[str] = []

    def capture(conn, cursor, statement, parameters, context, executemany) -> None:  # noqa: ANN001
        statements.append(statement)

    event.listen(engine, "before_cursor_execute", capture)
    try:
        response = api.get("/api/v1/catalog/sports", params={"category": "collective"})
    finally:
        event.remove(engine, "before_cursor_execute", capture)

    assert response.status_code == 200, response.text
    selects = [
        statement for statement in statements if statement.lstrip().upper().startswith("SELECT")
    ]
    assert len(selects) == 2
