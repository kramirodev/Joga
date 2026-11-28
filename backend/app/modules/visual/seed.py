"""Seed do baseline gratuito de identidade visual.

Os itens livres vêm do inventário de SVGs (`docs/ASSETS_SVG_INVENTARIO.md`):
modalidades, moldura bronze, tokens de cor, entrada de lobby, emote e badge de
beta. Itens de XP/passe entram depois pelo mesmo catálogo fechado.
"""

from __future__ import annotations

from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.visual.models import VisualCatalogItem

# (key, kind, name, asset_ref, season)
DEFAULT_VISUAL_ITEMS: tuple[tuple[str, str, str, str, str | None], ...] = (
    ("icon-sport-futebol-5x5", "icon", "Futebol 5x5", "icons/icon-sport-futebol-5x5.svg", None),
    ("icon-sport-volei-6x6", "icon", "Vôlei 6x6", "icons/icon-sport-volei-6x6.svg", None),
    (
        "icon-sport-futevolei-3x3",
        "icon",
        "Futevôlei 3x3",
        "icons/icon-sport-futevolei-3x3.svg",
        None,
    ),
    ("icon-app-escudo", "icon", "Escudo JOGA", "icons/icon-app-escudo.svg", None),
    ("frame-bronze", "frame", "Moldura bronze", "frames/frame-bronze.svg", None),
    ("accent-lime", "accent", "Lime", "tokens/accent-lime", None),
    ("accent-azul", "accent", "Azul", "tokens/accent-azul", None),
    ("accent-laranja", "accent", "Laranja", "tokens/accent-laranja", None),
    ("accent-roxo", "accent", "Roxo", "tokens/accent-roxo", None),
    ("accent-rosa", "accent", "Rosa", "tokens/accent-rosa", None),
    ("accent-ciano", "accent", "Ciano", "tokens/accent-ciano", None),
    ("entry-invite-lobby", "entry", "Convite de lobby", "identity/entry-invite-lobby.svg", None),
    ("emote-joinha", "emote", "Joinha", "emotes/emote-joinha.svg", None),
    ("badge-beta", "badge", "Beta", "badges/badge-beta.svg", None),
)

DEFAULT_IDENTITY_KEYS: dict[str, str] = {
    "icon": "icon-sport-futebol-5x5",
    "frame": "frame-bronze",
    "accent": "accent-lime",
    "entry": "entry-invite-lobby",
    "emote": "emote-joinha",
    "badge": "badge-beta",
}


def seed_default_visual_catalog(session: Session) -> None:
    """Garante o baseline gratuito. Idempotente."""

    existing = set(session.scalars(select(VisualCatalogItem.key)).all())
    for key, kind, name, asset_ref, season in DEFAULT_VISUAL_ITEMS:
        if key in existing:
            continue
        session.add(
            VisualCatalogItem(
                key=key,
                kind=kind,
                name=name,
                asset_ref=asset_ref,
                season=season,
                unlock_state="free",
                active=True,
            )
        )
    session.flush()


def default_identity_keys(session: Session) -> dict[str, str | None]:
    """Primeiro item ativo e gratuito de cada slot, na ordem do seed.

    Uma única consulta serve os seis slots: o cartão público lê este baseline
    a cada perfil sem identidade escolhida.
    """

    items = list(
        session.scalars(
            select(VisualCatalogItem)
            .where(
                VisualCatalogItem.active.is_(True),
                VisualCatalogItem.kind.in_(tuple(DEFAULT_IDENTITY_KEYS)),
            )
            .order_by(VisualCatalogItem.key)
        )
    )
    by_key = {item.key: item for item in items}
    keys: dict[str, str | None] = {}
    for slot in DEFAULT_IDENTITY_KEYS:
        item = by_key.get(DEFAULT_IDENTITY_KEYS[slot])
        if item is None:
            item = next(
                (
                    candidate
                    for candidate in items
                    if candidate.kind == slot and candidate.unlock_state == "free"
                ),
                None,
            )
        keys[slot] = item.key if item is not None else None
    return keys


def active_items(session: Session) -> Sequence[VisualCatalogItem]:
    return session.scalars(
        select(VisualCatalogItem)
        .where(VisualCatalogItem.active.is_(True))
        .order_by(VisualCatalogItem.kind, VisualCatalogItem.key)
    ).all()
