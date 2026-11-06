"""Papéis e capacidades das organizações.

As capacidades são verificadas no servidor em cada operação. O papel do
cliente nunca é aceito como prova de autorização.
"""

from __future__ import annotations

from enum import StrEnum


class Role(StrEnum):
    """Papéis suportados na Fase 11."""

    OWNER = "OWNER"
    ADMIN = "ADMIN"
    OPERATOR = "OPERATOR"


class Capability(StrEnum):
    """Ações autorizáveis dentro de uma organização."""

    ORGANIZATION_READ = "organization:read"
    ORGANIZATION_UPDATE = "organization:update"
    MEMBERS_READ = "members:read"
    MEMBERS_MANAGE = "members:manage"
    VENUES_READ = "venues:read"
    VENUES_MANAGE = "venues:manage"
    AUDIT_READ = "audit:read"


ROLE_CAPABILITIES: dict[Role, frozenset[Capability]] = {
    Role.OWNER: frozenset(Capability),
    Role.ADMIN: frozenset(
        {
            Capability.ORGANIZATION_READ,
            Capability.ORGANIZATION_UPDATE,
            Capability.MEMBERS_READ,
            Capability.MEMBERS_MANAGE,
            Capability.VENUES_READ,
            Capability.VENUES_MANAGE,
            Capability.AUDIT_READ,
        }
    ),
    Role.OPERATOR: frozenset(
        {
            Capability.ORGANIZATION_READ,
            Capability.MEMBERS_READ,
            Capability.VENUES_READ,
            Capability.VENUES_MANAGE,
        }
    ),
}


def capabilities_for(role: str | Role) -> frozenset[Capability]:
    """Retorna as capacidades do papel, rejeitando valores desconhecidos."""

    return ROLE_CAPABILITIES[Role(role)]


def can(role: str | Role, capability: Capability) -> bool:
    """Indica se o papel possui a capacidade informada."""

    return capability in capabilities_for(role)
