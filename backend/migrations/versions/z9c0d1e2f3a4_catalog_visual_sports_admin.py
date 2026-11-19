"""catálogo visual, esportes administráveis e preço automático

Revision ID: z9c0d1e2f3a4
Revises: y8b9c0d1e2f3
Create Date: 2026-11-20 00:00:00.000000

Adiciona o catálogo fechado de identidade visual, os campos administrativos de
esporte/formato e o seed baseline gratuito + futevôlei 3x3 inativo.
"""

from __future__ import annotations

import uuid
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "z9c0d1e2f3a4"
down_revision: str | Sequence[str] | None = "y8b9c0d1e2f3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

VISUAL_ITEMS: tuple[tuple[str, str, str, str, str | None], ...] = (
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


def upgrade() -> None:
    op.add_column(
        "sports",
        sa.Column(
            "icon_key",
            sa.String(length=64),
            nullable=False,
            server_default="icon-app-escudo",
        ),
    )
    op.add_column(
        "sports",
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
    )
    op.create_check_constraint(
        "sort_order_non_negative",
        "sports",
        "sort_order >= 0",
    )

    op.add_column(
        "sport_formats",
        sa.Column("players_per_team", sa.Integer(), nullable=False, server_default="5"),
    )
    op.execute("UPDATE sport_formats SET players_per_team = team_size")
    op.add_column(
        "sport_formats",
        sa.Column("period_count", sa.Integer(), nullable=False, server_default="1"),
    )
    op.add_column(
        "sport_formats",
        sa.Column(
            "score_model",
            sa.String(length=20),
            nullable=False,
            server_default="sets_points",
        ),
    )
    op.add_column(
        "sport_formats",
        sa.Column(
            "positions",
            sa.JSON(),
            nullable=False,
            server_default=sa.text("'[]'"),
        ),
    )
    op.create_check_constraint(
        "players_per_team_positive",
        "sport_formats",
        "players_per_team > 0",
    )
    op.create_check_constraint(
        "period_count_positive",
        "sport_formats",
        "period_count > 0",
    )
    op.create_check_constraint(
        "score_model_valid",
        "sport_formats",
        "score_model IN ('sets_points', 'goals')",
    )

    op.create_table(
        "visual_catalog_items",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("key", sa.String(length=64), nullable=False),
        sa.Column("kind", sa.String(length=12), nullable=False),
        sa.Column("name", sa.String(length=80), nullable=False),
        sa.Column("asset_ref", sa.String(length=200), nullable=False),
        sa.Column("season", sa.String(length=20), nullable=True),
        sa.Column("unlock_state", sa.String(length=10), nullable=False, server_default="free"),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.PrimaryKeyConstraint("id", name="pk_visual_catalog_items"),
        sa.UniqueConstraint("key", name="uq_visual_catalog_items_key"),
        sa.CheckConstraint(
            "kind IN ('icon', 'frame', 'accent', 'entry', 'emote', 'badge')",
            name="ck_visual_catalog_items_kind_valid",
        ),
        sa.CheckConstraint(
            "unlock_state IN ('free', 'xp', 'pass')",
            name="ck_visual_catalog_items_unlock_state_valid",
        ),
    )
    op.create_index(
        "ix_visual_catalog_items_kind_active",
        "visual_catalog_items",
        ["kind", "active"],
    )

    op.create_table(
        "user_visual_identity",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("icon_key", sa.String(length=64), nullable=False),
        sa.Column("frame_key", sa.String(length=64), nullable=False),
        sa.Column("accent_key", sa.String(length=64), nullable=False),
        sa.Column("entry_key", sa.String(length=64), nullable=False),
        sa.Column("emote_key", sa.String(length=64), nullable=False),
        sa.Column("badge_key", sa.String(length=64), nullable=False),
        sa.Column("catalog_version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.PrimaryKeyConstraint("user_id", name="pk_user_visual_identity"),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name="fk_user_visual_identity_user_id_users",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["icon_key"],
            ["visual_catalog_items.key"],
            name="fk_user_visual_identity_icon_key_visual_catalog_items",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["frame_key"],
            ["visual_catalog_items.key"],
            name="fk_user_visual_identity_frame_key_visual_catalog_items",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["accent_key"],
            ["visual_catalog_items.key"],
            name="fk_user_visual_identity_accent_key_visual_catalog_items",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["entry_key"],
            ["visual_catalog_items.key"],
            name="fk_user_visual_identity_entry_key_visual_catalog_items",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["emote_key"],
            ["visual_catalog_items.key"],
            name="fk_user_visual_identity_emote_key_visual_catalog_items",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["badge_key"],
            ["visual_catalog_items.key"],
            name="fk_user_visual_identity_badge_key_visual_catalog_items",
            ondelete="RESTRICT",
        ),
    )

    op.create_table(
        "user_visual_unlocks",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("item_id", sa.Uuid(), nullable=False),
        sa.Column("source", sa.String(length=20), nullable=False, server_default="xp"),
        sa.Column(
            "unlocked_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.PrimaryKeyConstraint("id", name="pk_user_visual_unlocks"),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name="fk_user_visual_unlocks_user_id_users",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["item_id"],
            ["visual_catalog_items.id"],
            name="fk_user_visual_unlocks_item_id_visual_catalog_items",
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint(
            "user_id",
            "item_id",
            name="uq_user_visual_unlocks_user_item",
        ),
    )
    op.create_index("ix_user_visual_unlocks_user", "user_visual_unlocks", ["user_id"])

    items_table = sa.table(
        "visual_catalog_items",
        sa.column("id", sa.Uuid()),
        sa.column("key", sa.String()),
        sa.column("kind", sa.String()),
        sa.column("name", sa.String()),
        sa.column("asset_ref", sa.String()),
        sa.column("season", sa.String()),
        sa.column("unlock_state", sa.String()),
        sa.column("active", sa.Boolean()),
    )
    op.bulk_insert(
        items_table,
        [
            {
                "id": uuid.uuid4(),
                "key": key,
                "kind": kind,
                "name": name,
                "asset_ref": asset_ref,
                "season": season,
                "unlock_state": "free",
                "active": True,
            }
            for key, kind, name, asset_ref, season in VISUAL_ITEMS
        ],
    )

    sports_table = sa.table(
        "sports",
        sa.column("id", sa.Uuid()),
        sa.column("slug", sa.String()),
        sa.column("name", sa.String()),
        sa.column("icon_key", sa.String()),
        sa.column("sort_order", sa.Integer()),
        sa.column("active", sa.Boolean()),
    )
    sport_id = uuid.uuid4()
    op.bulk_insert(
        sports_table,
        [
            {
                "id": sport_id,
                "slug": "futevolei",
                "name": "Futevôlei",
                "icon_key": "icon-sport-futevolei-3x3",
                "sort_order": 30,
                "active": False,
            }
        ],
    )

    formats_table = sa.table(
        "sport_formats",
        sa.column("id", sa.Uuid()),
        sa.column("sport_id", sa.Uuid()),
        sa.column("slug", sa.String()),
        sa.column("name", sa.String()),
        sa.column("team_size", sa.Integer()),
        sa.column("players_per_team", sa.Integer()),
        sa.column("total_participants", sa.Integer()),
        sa.column("play_minutes", sa.Integer()),
        sa.column("break_minutes", sa.Integer()),
        sa.column("duration_minutes", sa.Integer()),
        sa.column("period_count", sa.Integer()),
        sa.column("score_model", sa.String()),
        sa.column("positions", sa.JSON()),
        sa.column("version", sa.Integer()),
        sa.column("active", sa.Boolean()),
    )
    op.bulk_insert(
        formats_table,
        [
            {
                "id": uuid.uuid4(),
                "sport_id": sport_id,
                "slug": "futevolei-3x3",
                "name": "Futevôlei 3x3",
                "team_size": 3,
                "players_per_team": 3,
                "total_participants": 6,
                "play_minutes": 45,
                "break_minutes": 0,
                "duration_minutes": 45,
                "period_count": 1,
                "score_model": "sets_points",
                "positions": [],
                "version": 1,
                "active": True,
            }
        ],
    )


def downgrade() -> None:
    op.execute("DELETE FROM sports WHERE slug = 'futevolei'")

    op.drop_table("user_visual_unlocks")
    op.drop_table("user_visual_identity")
    op.drop_index("ix_visual_catalog_items_kind_active", table_name="visual_catalog_items")
    op.drop_table("visual_catalog_items")

    op.drop_constraint("score_model_valid", "sport_formats", type_="check")
    op.drop_constraint("period_count_positive", "sport_formats", type_="check")
    op.drop_constraint("players_per_team_positive", "sport_formats", type_="check")
    op.drop_column("sport_formats", "positions")
    op.drop_column("sport_formats", "score_model")
    op.drop_column("sport_formats", "period_count")
    op.drop_column("sport_formats", "players_per_team")

    op.drop_constraint("sort_order_non_negative", "sports", type_="check")
    op.drop_column("sports", "sort_order")
    op.drop_column("sports", "icon_key")
