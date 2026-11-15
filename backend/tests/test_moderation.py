"""Testes da moderação mínima (Fase 17A)."""

from __future__ import annotations

import uuid

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.modules.chat.models import LobbyMessage
from app.modules.identity.models import User
from app.modules.matchmaking.models import LobbyParticipant
from app.modules.moderation.models import ModerationOperator
from app.modules.moderation.service import (
    ModerationService,
    ReportConflict,
    ReportForbidden,
    ReportInvalid,
)
from app.modules.notifications.service import NotificationService
from app.modules.ratings.models import TrustAccount
from tests.helpers_results import make_token, make_user
from tests.test_bookings_api import api_client, bearer, setup_booking


def context_with_messages(db_session: Session) -> dict:
    context = setup_booking(db_session)
    lobby = context["lobbies"][0]
    message = LobbyMessage(
        lobby_id=lobby.id,
        sender_id=context["users"][1],
        body="Mensagem ofensiva de teste",
    )
    db_session.add(message)
    db_session.flush()
    context["message"] = message
    return context


def test_report_triages_and_limits_context(
    client: TestClient,
    db_session: Session,
) -> None:
    api = api_client(client, db_session)
    context = context_with_messages(db_session)
    response = api.post(
        "/api/v1/moderation/reports",
        headers=bearer(context["tokens"][0]),
        json={
            "target_user_id": str(context["users"][1]),
            "lobby_id": str(context["lobbies"][0].id),
            "category": "THREAT",
            "description": "Ameaça no chat do lobby",
            "message_ids": [str(context["message"].id)],
        },
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["severity"] == "HIGH"
    assert body["priority"] >= 70

    own = api.get("/api/v1/moderation/reports/me", headers=bearer(context["tokens"][0]))
    assert own.status_code == 200
    assert len(own.json()["reports"]) == 1

    other = api.get("/api/v1/moderation/reports/me", headers=bearer(context["tokens"][2]))
    assert other.status_code == 200
    assert other.json()["reports"] == []

    duplicate = api.post(
        "/api/v1/moderation/reports",
        headers=bearer(context["tokens"][0]),
        json={
            "target_user_id": str(context["users"][1]),
            "lobby_id": str(context["lobbies"][0].id),
            "category": "THREAT",
            "description": "Duplicada",
        },
    )
    assert duplicate.status_code == 409


def test_report_rejects_outsider_and_wrong_message(db_session: Session) -> None:
    context = context_with_messages(db_session)
    report_message = LobbyMessage(
        lobby_id=context["lobbies"][0].id,
        sender_id=context["users"][0],
        body="Mensagem do denunciante",
    )
    db_session.add(report_message)
    db_session.flush()
    service = ModerationService(db_session)

    try:
        service.create_report(
            uuid.uuid4(),
            target_user_id=context["users"][1],
            lobby_id=context["lobbies"][0].id,
            category="HARASSMENT",
            description="Fora do lobby",
        )
    except ReportForbidden:
        pass
    else:  # pragma: no cover
        raise AssertionError("outsider deveria ser rejeitado")

    try:
        service.create_report(
            context["users"][0],
            target_user_id=context["users"][1],
            lobby_id=context["lobbies"][0].id,
            category="HARASSMENT",
            description="Mensagem errada",
            message_ids=[report_message.id],
        )
    except ReportInvalid:
        pass
    else:  # pragma: no cover
        raise AssertionError("mensagem de outro autor deveria ser rejeitada")


def test_warning_creates_action_and_notification(db_session: Session) -> None:
    context = context_with_messages(db_session)
    service = ModerationService(db_session)
    report = service.create_report(
        context["users"][0],
        target_user_id=context["users"][1],
        lobby_id=context["lobbies"][0].id,
        category="HARASSMENT",
        description="Comportamento agressivo",
    )
    reviewed, action = service.review(
        report.id,
        operator="op1",
        decision="WARN",
        reason="Aviso formal",
        authorized_operators=frozenset({"op1"}),
    )
    assert reviewed.status == "RESOLVED"
    assert action is not None and action.action_type == "WARNING"
    notifications = NotificationService(db_session).list_for_user(context["users"][1])
    assert any(item.kind == "moderation_action" for item in notifications)


def test_ranked_restriction_is_reversible_by_appeal(db_session: Session) -> None:
    context = context_with_messages(db_session)
    service = ModerationService(db_session)
    report = service.create_report(
        context["users"][0],
        target_user_id=context["users"][1],
        lobby_id=context["lobbies"][0].id,
        category="THREAT",
        description="Ameaça grave",
    )
    _reviewed, action = service.review(
        report.id,
        operator="op1",
        decision="RESTRICT_RANKED",
        reason="Restrição de 7 dias",
        days=7,
        authorized_operators=frozenset({"op1"}),
    )
    assert action is not None
    account = db_session.get(TrustAccount, context["users"][1])
    assert account is not None and account.ranked_restricted_until is not None
    appeal = service.appeal(
        action.id,
        user_id=context["users"][1],
        reason="Quero revisar a decisão",
    )
    decided = service.review_appeal(
        appeal.id,
        operator="op1",
        decision="ACCEPTED",
        reason="Recurso procedente",
        authorized_operators=frozenset({"op1"}),
    )
    assert decided.status == "ACCEPTED"
    db_session.refresh(action)
    assert action.status == "REVOKED"


def test_report_rate_limit(db_session: Session) -> None:
    context = context_with_messages(db_session)
    service = ModerationService(db_session)
    targets = []
    for _ in range(6):
        user_id = make_user(db_session)
        db_session.add(
            LobbyParticipant(
                lobby_id=context["lobbies"][0].id,
                user_id=user_id,
                team=1,
                level="intermediate",
            )
        )
        targets.append(user_id)
    db_session.flush()
    for user_id in targets[:5]:
        service.create_report(
            context["users"][0],
            target_user_id=user_id,
            lobby_id=context["lobbies"][0].id,
            category="OTHER",
            description="Denúncia dentro do limite",
        )
    try:
        service.create_report(
            context["users"][0],
            target_user_id=targets[5],
            lobby_id=context["lobbies"][0].id,
            category="OTHER",
            description="Acima do limite",
        )
    except ReportConflict:
        pass
    else:  # pragma: no cover
        raise AssertionError("limite diário deveria ser aplicado")


def test_temporary_suspension_blocks_and_can_be_revoked(
    client: TestClient,
    db_session: Session,
) -> None:
    api = api_client(client, db_session)
    context = context_with_messages(db_session)
    service = ModerationService(db_session)
    report = service.create_report(
        context["users"][0],
        target_user_id=context["users"][1],
        lobby_id=context["lobbies"][0].id,
        category="THREAT",
        description="Ameaça grave",
    )
    _reviewed, action = service.review(
        report.id,
        operator="op1",
        decision="SUSPEND_TEMP",
        reason="Suspensão temporária",
        days=3,
        authorized_operators=frozenset({"op1"}),
    )
    assert action is not None
    db_session.commit()
    user = db_session.get(User, context["users"][1])
    assert user is not None and user.status == "suspended"

    blocked = api.get("/api/v1/auth/me", headers=bearer(context["tokens"][1]))
    assert blocked.status_code == 401

    actions = api.get(
        "/api/v1/moderation/actions/me",
        headers=bearer(context["tokens"][1]),
    )
    assert actions.status_code == 200, actions.text
    assert actions.json()["actions"][0]["action_type"] == "SUSPEND_TEMP"

    appeal = api.post(
        f"/api/v1/moderation/actions/{action.id}/appeal",
        json={"reason": "Quero contestar a suspensão"},
        headers=bearer(context["tokens"][1]),
    )
    assert appeal.status_code == 200, appeal.text
    reviewed = service.review_appeal(
        uuid.UUID(appeal.json()["id"]),
        operator="op1",
        decision="REJECTED",
        reason="Suspensão mantida",
        authorized_operators=frozenset({"op1"}),
    )
    assert reviewed.status == "REJECTED"
    db_session.commit()

    my_appeals = api.get(
        "/api/v1/moderation/appeals/me",
        headers=bearer(context["tokens"][1]),
    )
    assert my_appeals.status_code == 200, my_appeals.text
    assert my_appeals.json()["appeals"][0]["status"] == "REJECTED"
    assert my_appeals.json()["appeals"][0]["decision_reason"] == "Suspensão mantida"
    assert (
        api.get("/api/v1/me/notifications", headers=bearer(context["tokens"][1])).status_code == 401
    )

    other_user = api.post(
        f"/api/v1/moderation/actions/{action.id}/appeal",
        json={"reason": "Tentativa de terceiro"},
        headers=bearer(context["tokens"][0]),
    )
    assert other_user.status_code == 404

    my_reports = api.get(
        "/api/v1/moderation/reports/me",
        headers=bearer(context["tokens"][1]),
    )
    assert my_reports.status_code == 401

    service.revoke_action(action.id, operator="op1", reason="Recurso procedente")
    db_session.commit()
    allowed = api.get("/api/v1/auth/me", headers=bearer(context["tokens"][1]))
    assert allowed.status_code == 200


def test_false_report_cooldown(db_session: Session) -> None:
    context = context_with_messages(db_session)
    service = ModerationService(db_session)
    for index in range(3):
        report = service.create_report(
            context["users"][0],
            target_user_id=context["users"][1],
            lobby_id=context["lobbies"][0].id,
            category="OTHER",
            description=f"Denúncia improcedente {index}",
        )
        service.review(
            report.id,
            operator="op1",
            decision="DISMISS",
            reason="Improcedente",
            authorized_operators=frozenset({"op1"}),
        )
    try:
        service.create_report(
            context["users"][0],
            target_user_id=context["users"][2],
            lobby_id=context["lobbies"][0].id,
            category="OTHER",
            description="Nova denúncia",
        )
    except ReportConflict:
        pass
    else:  # pragma: no cover
        raise AssertionError("cooldown de denunciante deveria ser aplicado")


def test_admin_queue_notification_and_decision(
    client: TestClient,
    db_session: Session,
) -> None:
    api = api_client(client, db_session)
    context = context_with_messages(db_session)
    admin_id = make_user(db_session)
    admin_token = make_token(db_session, admin_id)
    db_session.add(ModerationOperator(user_id=admin_id, role="ADMIN", active=True))
    db_session.flush()

    report = api.post(
        "/api/v1/moderation/reports",
        headers=bearer(context["tokens"][0]),
        json={
            "target_user_id": str(context["users"][1]),
            "lobby_id": str(context["lobbies"][0].id),
            "category": "THREAT",
            "description": "Ameaça no chat",
        },
    )
    assert report.status_code == 201, report.text
    notification = NotificationService(db_session).list_for_user(
        admin_id,
        channel="moderation",
    )
    assert any(item.kind == "moderation_report" for item in notification)

    queue = api.get("/api/v1/moderation/queue", headers=bearer(admin_token))
    assert queue.status_code == 200, queue.text
    body = queue.json()
    assert body["stats"]["open"] >= 1
    assert body["reports"][0]["description"] == "Ameaça no chat"

    report_id = body["reports"][0]["id"]
    detail = api.get(f"/api/v1/moderation/reports/{report_id}", headers=bearer(admin_token))
    assert detail.status_code == 200, detail.text
    assert detail.json()["category"] == "THREAT"

    decision = api.post(
        f"/api/v1/moderation/reports/{report_id}/decision",
        headers=bearer(admin_token),
        json={"decision": "WARN", "reason": "Aviso formal"},
    )
    assert decision.status_code == 200, decision.text
    assert decision.json()["status"] == "RESOLVED"

    after = api.get("/api/v1/moderation/queue", headers=bearer(admin_token))
    assert after.json()["reports"] == []

    actions = api.get(
        "/api/v1/moderation/actions/me",
        headers=bearer(context["tokens"][1]),
    )
    assert actions.status_code == 200, actions.text
    action_id = actions.json()["actions"][0]["id"]

    appeal = api.post(
        f"/api/v1/moderation/actions/{action_id}/appeal",
        headers=bearer(context["tokens"][1]),
        json={"reason": "Quero contestar o aviso"},
    )
    assert appeal.status_code == 200, appeal.text
    admin_notifications = NotificationService(db_session).list_for_user(
        admin_id,
        channel="moderation",
    )
    assert any(item.kind == "moderation_appeal" for item in admin_notifications)
    player_notifications = NotificationService(db_session).list_for_user(admin_id)
    assert all(
        item.kind not in {"moderation_report", "moderation_appeal"} for item in player_notifications
    )

    appeal_decision = api.post(
        f"/api/v1/moderation/appeals/{appeal.json()['id']}/decision",
        headers=bearer(admin_token),
        json={"decision": "REJECTED", "reason": "Aviso mantido"},
    )
    assert appeal_decision.status_code == 200, appeal_decision.text
    target_notifications = NotificationService(db_session).list_for_user(context["users"][1])
    assert any(item.kind == "moderation_appeal_result" for item in target_notifications)


def test_non_moderator_cannot_read_queue(client: TestClient, db_session: Session) -> None:
    api = api_client(client, db_session)
    context = context_with_messages(db_session)
    response = api.get("/api/v1/moderation/queue", headers=bearer(context["tokens"][0]))
    assert response.status_code == 403
    assert response.json()["detail"]["code"] == "moderator_required"


def test_admin_can_add_operator(client: TestClient, db_session: Session) -> None:
    api = api_client(client, db_session)
    context_with_messages(db_session)
    admin_id = make_user(db_session)
    admin_token = make_token(db_session, admin_id)
    db_session.add(ModerationOperator(user_id=admin_id, role="ADMIN", active=True))
    db_session.flush()
    new_operator = make_user(db_session)

    created = api.post(
        "/api/v1/moderation/operators",
        headers=bearer(admin_token),
        json={"user_id": str(new_operator), "role": "MODERATOR"},
    )
    assert created.status_code == 201, created.text
    assert created.json()["role"] == "MODERATOR"

    token = make_token(db_session, new_operator)
    me = api.get("/api/v1/moderation/me", headers=bearer(token))
    assert me.status_code == 200
    assert me.json()["role"] == "MODERATOR"


def test_admin_cannot_add_unknown_operator(client: TestClient, db_session: Session) -> None:
    api = api_client(client, db_session)
    admin_id = make_user(db_session)
    admin_token = make_token(db_session, admin_id)
    db_session.add(ModerationOperator(user_id=admin_id, role="ADMIN", active=True))
    db_session.flush()

    response = api.post(
        "/api/v1/moderation/operators",
        headers=bearer(admin_token),
        json={"user_id": str(uuid.uuid4()), "role": "MODERATOR"},
    )
    assert response.status_code == 404
    assert response.json()["detail"]["code"] == "not_found"
