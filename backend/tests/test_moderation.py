"""Testes da moderação mínima (Fase 17A)."""

from __future__ import annotations

import uuid

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.modules.chat.models import LobbyMessage
from app.modules.matchmaking.models import LobbyParticipant
from app.modules.moderation.service import (
    ModerationService,
    ReportConflict,
    ReportForbidden,
    ReportInvalid,
)
from app.modules.notifications.service import NotificationService
from app.modules.ratings.models import TrustAccount
from tests.helpers_results import make_user
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
