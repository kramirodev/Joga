"""Busca de jogador por nome/tag, relação de amizade e privacidade."""

from __future__ import annotations

import uuid
from collections.abc import Iterator

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.infrastructure.database.dependency import get_session
from app.modules.clans.models import Clan, ClanMember
from app.modules.identity.models import User
from app.modules.profile.models import UserProfile
from app.modules.social.models import Friendship, UserBlock
from app.modules.social.service import ordered_pair
from tests.helpers_results import make_token, make_user


def api_client(client: TestClient, db_session: Session) -> TestClient:
    def override_session() -> Iterator[Session]:
        yield db_session

    client.app.dependency_overrides[get_session] = override_session
    return client


def bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def add_player(
    session: Session,
    display_name: str | None,
    *,
    status: str = "active",
    tag: str | None = None,
    email: str | None = None,
) -> uuid.UUID:
    user_id = make_user(session, available=False)
    user = session.get(User, user_id)
    assert user is not None
    user.status = status
    if tag is not None:
        user.tag = tag
    if email is not None:
        user.email = email
    session.add(UserProfile(user_id=user_id, display_name=display_name))
    session.flush()
    return user_id


def search(api: TestClient, token: str, query: str, **params: object):
    return api.get(
        "/api/v1/users/search",
        headers=bearer(token),
        params={"q": query, **params},
    )


def test_search_by_partial_name_is_case_insensitive_and_ordered(
    client: TestClient,
    db_session: Session,
) -> None:
    api = api_client(client, db_session)
    actor = make_user(db_session)
    token = make_token(db_session, actor)
    beta = add_player(db_session, "BUSCA BETA")
    alfa = add_player(db_session, "BUSCA ALFA")
    add_player(db_session, "OUTRO NOME")

    response = search(api, token, "busca")

    assert response.status_code == 200, response.text
    body = response.json()["results"]
    assert [item["user_id"] for item in body] == [str(alfa), str(beta)]
    assert [item["display_name"] for item in body] == ["BUSCA ALFA", "BUSCA BETA"]
    assert {item["relation"] for item in body} == {"none"}


def test_search_keeps_accents_and_matches_different_case(
    client: TestClient,
    db_session: Session,
) -> None:
    api = api_client(client, db_session)
    token = make_token(db_session, make_user(db_session))
    target = add_player(db_session, "JOÃO DA SILVA")

    lower = search(api, token, "joão")
    upper = search(api, token, "SILVA")

    assert lower.status_code == 200, lower.text
    assert upper.status_code == 200, upper.text
    assert [item["user_id"] for item in lower.json()["results"]] == [str(target)]
    assert [item["user_id"] for item in upper.json()["results"]] == [str(target)]


def test_search_escapes_like_wildcards(
    client: TestClient,
    db_session: Session,
) -> None:
    api = api_client(client, db_session)
    token = make_token(db_session, make_user(db_session))
    literal = add_player(db_session, "BUSCA 100% LITERAL")
    add_player(db_session, "BUSCA 1000 COMUM")

    response = search(api, token, "100%")

    assert response.status_code == 200, response.text
    assert [item["user_id"] for item in response.json()["results"]] == [str(literal)]


def test_search_by_exact_tag_with_or_without_hash(
    client: TestClient,
    db_session: Session,
) -> None:
    api = api_client(client, db_session)
    token = make_token(db_session, make_user(db_session))
    target = add_player(db_session, "TAG EXATA", tag="#9F55A2C1")

    for query in ("9F55A2C1", "#9F55A2C1", "#9f55a2c1", "nome#9f55a2c1"):
        response = search(api, token, query)
        assert response.status_code == 200, response.text
        body = response.json()["results"]
        assert [item["user_id"] for item in body] == [str(target)], query
        assert body[0]["tag"] == "#9F55A2C1"

    missing = search(api, token, "#FFFFFFFF")
    assert missing.status_code == 200
    assert missing.json()["results"] == []


def test_search_reports_relations_and_excludes_self_and_blocks(
    client: TestClient,
    db_session: Session,
) -> None:
    api = api_client(client, db_session)
    actor = add_player(db_session, "RELACAO ATOR")
    token = make_token(db_session, actor)
    friend = add_player(db_session, "RELACAO AMIGO")
    incoming = add_player(db_session, "RELACAO RECEBIDO")
    outgoing = add_player(db_session, "RELACAO ENVIADO")
    none_relation = add_player(db_session, "RELACAO NENHUMA")
    blocked_by_me = add_player(db_session, "RELACAO BLOQUEADO")
    blocked_me = add_player(db_session, "RELACAO BLOQUEADOR")

    low, high = ordered_pair(actor, friend)
    db_session.add(
        Friendship(
            user_low_id=low,
            user_high_id=high,
            requested_by=actor,
            status="ACCEPTED",
        )
    )
    low, high = ordered_pair(actor, incoming)
    db_session.add(
        Friendship(
            user_low_id=low,
            user_high_id=high,
            requested_by=incoming,
            status="PENDING",
        )
    )
    low, high = ordered_pair(actor, outgoing)
    db_session.add(
        Friendship(
            user_low_id=low,
            user_high_id=high,
            requested_by=actor,
            status="PENDING",
        )
    )
    db_session.add(UserBlock(blocker_id=actor, blocked_id=blocked_by_me))
    db_session.add(UserBlock(blocker_id=blocked_me, blocked_id=actor))
    db_session.flush()

    response = search(api, token, "RELACAO", limit=20)

    assert response.status_code == 200, response.text
    results = {item["user_id"]: item["relation"] for item in response.json()["results"]}
    assert results == {
        str(friend): "friend",
        str(incoming): "incoming_request",
        str(outgoing): "outgoing_request",
        str(none_relation): "none",
    }


def test_search_excludes_suspended_and_deleted_accounts(
    client: TestClient,
    db_session: Session,
) -> None:
    api = api_client(client, db_session)
    token = make_token(db_session, make_user(db_session))
    active = add_player(db_session, "FANTASMA ATIVO")
    add_player(db_session, "FANTASMA SUSPENSO", status="suspended")
    add_player(db_session, "FANTASMA DELETADO", status="deleted")

    response = search(api, token, "FANTASMA")

    assert response.status_code == 200, response.text
    assert [item["user_id"] for item in response.json()["results"]] == [str(active)]


def test_search_response_never_exposes_pii(
    client: TestClient,
    db_session: Session,
) -> None:
    api = api_client(client, db_session)
    token = make_token(db_session, make_user(db_session))
    add_player(
        db_session,
        "PII TESTE",
        email="pii@example.com",
    )

    response = search(api, token, "PII")

    assert response.status_code == 200, response.text
    item = response.json()["results"][0]
    assert set(item) == {"user_id", "display_name", "tag", "relation"}
    assert item["display_name"] == "PII TESTE"
    assert "pii@example.com" not in response.text
    for forbidden_key in ("email", "phone", "cpf", "status", "lat", "lng", "coordinates"):
        assert forbidden_key not in item


def test_search_validates_query_and_authentication(
    client: TestClient,
    db_session: Session,
) -> None:
    api = api_client(client, db_session)
    token = make_token(db_session, make_user(db_session))
    db_session.add(UserProfile(user_id=make_user(db_session, available=False), display_name="ABC"))
    db_session.flush()

    assert search(api, token, "ab").status_code == 422
    assert search(api, token, "a" * 41).status_code == 422
    spaces = search(api, token, "   ")
    assert spaces.status_code == 422
    assert spaces.json()["detail"]["code"] == "invalid_search_query"
    assert client.get("/api/v1/users/search", params={"q": "abc"}).status_code == 401


def test_profile_update_canonicalizes_name_and_search_is_case_insensitive(
    client: TestClient,
    db_session: Session,
) -> None:
    """Regressão: escrita do perfil canoniza; busca por nome/tag não diferencia caixa."""

    api = api_client(client, db_session)
    actor_token = make_token(db_session, add_player(db_session, "BUSCADOR"))
    target = add_player(db_session, "NOME ANTIGO", tag="#ABCD1234")
    target_token = make_token(db_session, target)

    updated = api.put(
        "/api/v1/me/profile",
        headers=bearer(target_token),
        json={"display_name": "  novo   jogador ", "bio": None},
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["display_name"] == "NOVO JOGADOR"
    profile = db_session.get(UserProfile, target)
    assert profile is not None
    assert profile.display_name == "NOVO JOGADOR"

    for query in ("novo jogador", "NOVO", "abcd1234", "#abcd1234"):
        response = search(api, actor_token, query)
        assert response.status_code == 200, response.text
        results = response.json()["results"]
        assert [item["user_id"] for item in results] == [str(target)], query
        assert results[0]["display_name"] == "NOVO JOGADOR"
        assert results[0]["tag"] == "#ABCD1234"


def test_public_player_shape_tag_relation_and_clan(
    client: TestClient,
    db_session: Session,
) -> None:
    api = api_client(client, db_session)
    actor = add_player(db_session, "VISITANTE")
    token = make_token(db_session, actor)
    target = add_player(
        db_session,
        "PERFIL PUBLICO",
        tag="#FEED1234",
        email="pii@example.com",
    )
    low, high = ordered_pair(actor, target)
    db_session.add(
        Friendship(
            user_low_id=low,
            user_high_id=high,
            requested_by=actor,
            status="ACCEPTED",
        )
    )
    clan = Clan(name="Clã Público", tag="#PUB", created_by=target)
    db_session.add(clan)
    db_session.flush()
    db_session.add(ClanMember(clan_id=clan.id, user_id=target, role="owner", status="active"))
    db_session.flush()

    response = api.get(f"/api/v1/users/{target}", headers=bearer(token))

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["user_id"] == str(target)
    assert body["display_name"] == "PERFIL PUBLICO"
    assert body["tag"] == "#FEED1234"
    assert body["relation"] == "friend"
    assert body["clan"] == {"id": str(clan.id), "name": "Clã Público", "tag": "#PUB"}
    assert body["card"]["visual"]["icon_key"] is not None
    assert body["card"]["badges"] == []
    assert set(body) == {"user_id", "display_name", "tag", "relation", "clan", "card"}
    assert set(body["clan"]) == {"id", "name", "tag"}
    assert set(body["card"]) == {
        "theme_id",
        "visual",
        "tier",
        "level",
        "qualifier",
        "season_label",
        "record",
        "win_streak",
        "badges",
    }
    for forbidden_key in (
        "email",
        "phone",
        "cpf",
        "status",
        "lat",
        "lng",
        "coordinates",
        "mmr",
    ):
        assert forbidden_key not in body
    assert "pii@example.com" not in response.text


def test_public_player_reports_relation_and_null_clan(
    client: TestClient,
    db_session: Session,
) -> None:
    api = api_client(client, db_session)
    actor = add_player(db_session, "ATOR RELACAO PUBLICA")
    token = make_token(db_session, actor)
    incoming = add_player(db_session, "PEDIDO RECEBIDO")
    outgoing = add_player(db_session, "PEDIDO ENVIADO")
    stranger = add_player(db_session, "SEM RELACAO")

    low, high = ordered_pair(actor, incoming)
    db_session.add(
        Friendship(
            user_low_id=low,
            user_high_id=high,
            requested_by=incoming,
            status="PENDING",
        )
    )
    low, high = ordered_pair(actor, outgoing)
    db_session.add(
        Friendship(
            user_low_id=low,
            user_high_id=high,
            requested_by=actor,
            status="PENDING",
        )
    )
    db_session.flush()

    expected = {
        incoming: "incoming_request",
        outgoing: "outgoing_request",
        stranger: "none",
    }
    for user_id, relation in expected.items():
        body = api.get(f"/api/v1/users/{user_id}", headers=bearer(token)).json()
        assert body["relation"] == relation
        assert body["clan"] is None


def test_public_player_is_404_for_missing_inactive_and_blocked(
    client: TestClient,
    db_session: Session,
) -> None:
    api = api_client(client, db_session)
    actor = add_player(db_session, "ATOR BLOQUEIO")
    token = make_token(db_session, actor)
    suspended = add_player(db_session, "SUSPENSO PUBLICO", status="suspended")
    deleted = add_player(db_session, "DELETADO PUBLICO", status="deleted")
    blocked_by_me = add_player(db_session, "BLOQUEADO POR MIM")
    blocked_me = add_player(db_session, "ME BLOQUEOU")
    db_session.add(UserBlock(blocker_id=actor, blocked_id=blocked_by_me))
    db_session.add(UserBlock(blocker_id=blocked_me, blocked_id=actor))
    db_session.flush()

    for user_id in (
        uuid.uuid4(),
        suspended,
        deleted,
        blocked_by_me,
        blocked_me,
    ):
        response = api.get(f"/api/v1/users/{user_id}", headers=bearer(token))
        assert response.status_code == 404, response.text
        assert response.json() == {"detail": {"code": "user_not_found"}}

    missing = uuid.uuid4()
    assert client.get(f"/api/v1/users/{missing}").status_code == 401


def test_search_is_rate_limited_per_user(
    client: TestClient,
    db_session: Session,
) -> None:
    api = api_client(client, db_session)
    token = make_token(db_session, make_user(db_session))
    add_player(db_session, "LIMITE TESTE")

    for _ in range(60):
        assert search(api, token, "LIMITE").status_code == 200

    blocked = search(api, token, "LIMITE")

    assert blocked.status_code == 429
    assert blocked.json() == {"detail": {"code": "rate_limited"}}
    assert int(blocked.headers["Retry-After"]) >= 1
