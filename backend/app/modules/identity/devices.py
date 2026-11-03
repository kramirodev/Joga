"""Dispositivos vinculados ao usuário e revogação de sessões por dispositivo."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.identity.clock import ensure_utc, utcnow
from app.modules.identity.models import Device
from app.modules.identity.models import Session as SessionRecord

DEVICE_PLATFORMS = {"android", "ios", "web", "unknown"}


class DeviceError(Exception):
    """Erro base de dispositivos."""


class InvalidDevice(DeviceError):
    """Plataforma ou nome inválido."""


class DeviceNotFound(DeviceError):
    """Dispositivo inexistente ou de outro usuário."""


class DeviceService:
    """Registra, lista e revoga dispositivos do usuário."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def register(
        self,
        user_id: uuid.UUID,
        name: str,
        platform: str = "unknown",
        *,
        now: datetime | None = None,
    ) -> Device:
        if platform not in DEVICE_PLATFORMS:
            raise InvalidDevice("plataforma inválida")
        cleaned = name.strip()[:80] or "Dispositivo"
        moment = ensure_utc(now or utcnow())
        device = Device(
            user_id=user_id,
            platform=platform,
            name=cleaned,
            created_at=moment,
            last_seen_at=moment,
        )
        self._session.add(device)
        self._session.flush()
        return device

    def list(self, user_id: uuid.UUID) -> list[Device]:
        return list(
            self._session.scalars(
                select(Device)
                .where(Device.user_id == user_id, Device.revoked_at.is_(None))
                .order_by(Device.created_at)
            )
        )

    def revoke(
        self,
        user_id: uuid.UUID,
        device_id: uuid.UUID,
        *,
        now: datetime | None = None,
    ) -> None:
        device = self._session.get(Device, device_id)
        if device is None or device.user_id != user_id:
            raise DeviceNotFound("dispositivo não encontrado")
        moment = ensure_utc(now or utcnow())
        if device.revoked_at is None:
            device.revoked_at = moment

        sessions = self._session.scalars(
            select(SessionRecord).where(
                SessionRecord.device_id == device_id,
                SessionRecord.revoked_at.is_(None),
            )
        )
        for row in sessions:
            row.revoked_at = moment
            row.revoked_reason = "device_revoked"
        self._session.flush()
