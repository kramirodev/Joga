"""Matriz RBAC ponta a ponta (ADR 0078 §6).

Cada papel é exercitado via HTTP com o mesmo ``TestClient`` e as mesmas
fixtures dos testes de moderação, observabilidade, admin e organizações.
Nenhum serviço externo é chamado: o lookup de CNPJ é o fake de teste.
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.infrastructure.database.dependency import get_session
from app.modules.moderation.models import ModerationOperator
from app.modules.organizations.dependency import get_cnpj_lookup
from tests.cnpj_helpers import FakeCnpjLookup, make_cnpj_user
from tests.helpers_results import make_token, make_user
from tests.test_organizations import create_organization, create_venue

OBSERVABILITY_SUMMARY = "/api/v1/admin/observability/summary?window=24h"
OPERATOR_ROLES = ("player", "moderator", "moderation_admin", "organizer", "platform_admin")


@dataclass(frozen=True)
class Actor:
    user_id: UUID
    token: str

    @property
    def headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.token}"}


@dataclass(frozen=True)
class RbacWorld:
    api: TestClient
    players: dict[str, Actor]
    organization_id: str
    venue_id: str


def actor_for(db_session: Session, user_id: UUID) -> Actor:
    return Actor(user_id=user_id, token=make_token(db_session, user_id))


def rbac_client(
    client: TestClient,
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
    *,
    platform_admins: str = "",
    moderation_admin_user_ids: str = "",
) -> TestClient:
    """Cliente com sessão isolada, allowlists e lookup de CNPJ sem rede."""

    settings = Settings(
        _env_file=None,
        platform_admins=platform_admins,
        moderation_admin_user_ids=moderation_admin_user_ids,
        ticket_purchase_enabled=True,
    )

    def override_session() -> Iterator[Session]:
        yield db_session

    client.app.dependency_overrides[get_session] = override_session
    client.app.dependency_overrides[get_settings] = lambda: settings
    client.app.dependency_overrides[get_cnpj_lookup] = lambda: FakeCnpjLookup()
    # O serviço de moderação lê ``get_settings`` diretamente (ADR 0066).
    monkeypatch.setattr("app.modules.moderation.service.get_settings", lambda: settings)
    return client


@pytest.fixture
def rbac(
    client: TestClient,
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> RbacWorld:
    player_id = make_user(db_session)
    moderator_id = make_user(db_session)
    moderation_admin_id = make_user(db_session)
    organizer_id = make_cnpj_user(db_session)
    platform_admin_id = make_user(db_session)
    db_session.add_all(
        [
            ModerationOperator(user_id=moderator_id, role="MODERATOR", active=True),
            ModerationOperator(user_id=moderation_admin_id, role="ADMIN", active=True),
        ]
    )
    db_session.flush()

    api = rbac_client(
        client,
        db_session,
        monkeypatch,
        platform_admins=str(platform_admin_id),
    )
    organizer = actor_for(db_session, organizer_id)
    organization = create_organization(api, organizer.token, name="Arena RBAC")
    venue = create_venue(api, organizer.token, organization["id"], name="Quadra RBAC")

    return RbacWorld(
        api=api,
        players={
            "player": actor_for(db_session, player_id),
            "moderator": actor_for(db_session, moderator_id),
            "moderation_admin": actor_for(db_session, moderation_admin_id),
            "organizer": organizer,
            "platform_admin": actor_for(db_session, platform_admin_id),
        },
        organization_id=organization["id"],
        venue_id=venue["id"],
    )


def assert_forbidden(response, code: str) -> None:
    assert response.status_code == 403, response.text
    assert response.json() == {"detail": {"code": code}}


def assert_no_platform_access(api: TestClient, actor: Actor) -> None:
    for path in ("/api/v1/admin/users", "/api/v1/admin/venues", OBSERVABILITY_SUMMARY):
        response = api.get(path, headers=actor.headers)
        assert response.status_code == 403, (path, response.text)
        assert response.json() == {"detail": {"code": "forbidden"}}, (path, response.text)


def test_jogador_nao_acessa_moderacao_nem_plataforma(rbac: RbacWorld) -> None:
    player = rbac.players["player"]

    assert_forbidden(
        rbac.api.get("/api/v1/moderation/queue", headers=player.headers),
        "moderator_required",
    )
    assert_no_platform_access(rbac.api, player)


def test_moderador_le_fila_mas_nao_gerencia_operadores(rbac: RbacWorld) -> None:
    moderator = rbac.players["moderator"]
    target = rbac.players["player"].user_id

    queue = rbac.api.get("/api/v1/moderation/queue", headers=moderator.headers)
    assert queue.status_code == 200, queue.text

    created = rbac.api.post(
        "/api/v1/moderation/operators",
        headers=moderator.headers,
        json={"user_id": str(target), "role": "MODERATOR"},
    )
    assert_forbidden(created, "admin_required")

    removed = rbac.api.delete(
        f"/api/v1/moderation/operators/{target}",
        headers=moderator.headers,
    )
    assert_forbidden(removed, "admin_required")

    assert_no_platform_access(rbac.api, moderator)


def test_admin_de_moderacao_gerencia_operadores_sem_admin_de_plataforma(
    rbac: RbacWorld,
    db_session: Session,
) -> None:
    admin = rbac.players["moderation_admin"]
    target = make_user(db_session)

    me = rbac.api.get("/api/v1/moderation/me", headers=admin.headers)
    assert me.status_code == 200, me.text
    assert me.json()["role"] == "ADMIN"

    created = rbac.api.post(
        "/api/v1/moderation/operators",
        headers=admin.headers,
        json={"user_id": str(target), "role": "MODERATOR"},
    )
    assert created.status_code == 201, created.text
    assert created.json()["role"] == "MODERATOR"

    removed = rbac.api.delete(
        f"/api/v1/moderation/operators/{target}",
        headers=admin.headers,
    )
    assert removed.status_code == 204, removed.text

    assert_no_platform_access(rbac.api, admin)


def test_organizador_gerencia_a_propria_organizacao_sem_poderes_globais(
    rbac: RbacWorld,
) -> None:
    organizer = rbac.players["organizer"]

    own = rbac.api.get(
        f"/api/v1/organizations/{rbac.organization_id}",
        headers=organizer.headers,
    )
    assert own.status_code == 200, own.text
    assert own.json()["id"] == rbac.organization_id

    venues = rbac.api.get(
        f"/api/v1/organizations/{rbac.organization_id}/venues",
        headers=organizer.headers,
    )
    assert venues.status_code == 200, venues.text
    assert [item["id"] for item in venues.json()["venues"]] == [rbac.venue_id]

    renamed = rbac.api.patch(
        f"/api/v1/organizations/{rbac.organization_id}/venues/{rbac.venue_id}",
        headers=organizer.headers,
        json={"name": "Quadra RBAC renomeada"},
    )
    assert renamed.status_code == 200, renamed.text
    assert renamed.json()["name"] == "Quadra RBAC renomeada"

    assert_forbidden(
        rbac.api.get("/api/v1/moderation/queue", headers=organizer.headers),
        "moderator_required",
    )
    assert_no_platform_access(rbac.api, organizer)


def test_admin_de_plataforma_tem_acesso_total(
    rbac: RbacWorld,
    db_session: Session,
) -> None:
    platform_admin = rbac.players["platform_admin"]

    # ADR 0066: plataforma modera por definição, sem linha de operador.
    assert db_session.get(ModerationOperator, platform_admin.user_id) is None
    me = rbac.api.get("/api/v1/moderation/me", headers=platform_admin.headers)
    assert me.status_code == 200, me.text
    assert me.json() == {"user_id": str(platform_admin.user_id), "role": "ADMIN"}

    queue = rbac.api.get("/api/v1/moderation/queue", headers=platform_admin.headers)
    assert queue.status_code == 200, queue.text

    users = rbac.api.get("/api/v1/admin/users", headers=platform_admin.headers)
    assert users.status_code == 200, users.text

    venues = rbac.api.get("/api/v1/admin/venues", headers=platform_admin.headers)
    assert venues.status_code == 200, venues.text

    summary = rbac.api.get(OBSERVABILITY_SUMMARY, headers=platform_admin.headers)
    assert summary.status_code == 200, summary.text


AREAS: dict[str, tuple[str, str]] = {
    "moderation_read": ("GET", "/api/v1/moderation/queue"),
    "moderation_manage": ("GET", "/api/v1/moderation/operators"),
    "platform_users": ("GET", "/api/v1/admin/users"),
    "platform_venues": ("GET", "/api/v1/admin/venues"),
    "observability": ("GET", OBSERVABILITY_SUMMARY),
}

# Papel × área com a expectativa explícita: (status, código) ou (200, None).
EXPECTED: dict[str, dict[str, tuple[int, str | None]]] = {
    "player": {
        "moderation_read": (403, "moderator_required"),
        "moderation_manage": (403, "moderator_required"),
        "platform_users": (403, "forbidden"),
        "platform_venues": (403, "forbidden"),
        "observability": (403, "forbidden"),
    },
    "moderator": {
        "moderation_read": (200, None),
        "moderation_manage": (403, "admin_required"),
        "platform_users": (403, "forbidden"),
        "platform_venues": (403, "forbidden"),
        "observability": (403, "forbidden"),
    },
    "moderation_admin": {
        "moderation_read": (200, None),
        "moderation_manage": (200, None),
        "platform_users": (403, "forbidden"),
        "platform_venues": (403, "forbidden"),
        "observability": (403, "forbidden"),
    },
    "organizer": {
        "moderation_read": (403, "moderator_required"),
        "moderation_manage": (403, "moderator_required"),
        "platform_users": (403, "forbidden"),
        "platform_venues": (403, "forbidden"),
        "observability": (403, "forbidden"),
    },
    "platform_admin": {
        "moderation_read": (200, None),
        "moderation_manage": (200, None),
        "platform_users": (200, None),
        "platform_venues": (200, None),
        "observability": (200, None),
    },
}


@pytest.mark.parametrize("role", OPERATOR_ROLES)
def test_matriz_rbac_por_papel(rbac: RbacWorld, role: str) -> None:
    """Regressão da matriz: mexer num guard deve quebrar este teste."""

    actor = rbac.players[role]
    assert set(EXPECTED[role]) == set(AREAS)

    for area, (status_code, code) in EXPECTED[role].items():
        method, path = AREAS[area]
        response = rbac.api.request(method, path, headers=actor.headers)
        assert response.status_code == status_code, (role, area, response.text)
        if code is not None:
            assert response.json() == {"detail": {"code": code}}, (
                role,
                area,
                response.text,
            )
