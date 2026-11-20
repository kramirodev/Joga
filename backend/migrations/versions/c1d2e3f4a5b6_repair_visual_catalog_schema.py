"""repara o schema do catálogo visual em bancos antigos

Revision ID: c1d2e3f4a5b6
Revises: b1c2d3e4f5a6
Create Date: 2026-11-20 00:00:00.000000

A revisão ``a0b1c2d3e4f5`` foi reancorada em ``z9c0d1e2f3a4``. Bancos que já
haviam aplicado ``a0b1c2d3e4f5`` antes de ``z9c0d1e2f3a4`` existir avançam
direto para ``b1c2d3e4f5a6`` sem os objetos de ``z9``; o Alembic não reaplica
uma revisão ancestral retroativamente.

Esta revisão é um reparo aditivo e idempotente. Ela garante colunas,
constraints, índices, tabelas e seeds de ``z9`` que estiverem faltando, sem
reescrever ``z9``/``a0b1c2d3e4f5`` e sem apagar dados. Em banco criado do zero
nada é alterado. O downgrade é intencionalmente no-op: o reparo não tem como
distinguir o que ele criou do que já pertencia a ``z9`` e nunca deve remover
dados ou objetos de uma migração ancestral.
"""

from __future__ import annotations

import uuid
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.engine import Connection

revision: str = "c1d2e3f4a5b6"
down_revision: str | Sequence[str] | None = "b1c2d3e4f5a6"
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

# Nomes gerados pela convenção de nomes do metadata do projeto para as
# constraints de ``visual_catalog_items``. O nome da constraint de
# ``unlock_state`` é truncado pelo SQLAlchemy por exceder 63 caracteres.
VISUAL_KIND_CHECK = "ck_visual_catalog_items_ck_visual_catalog_items_kind_valid"
VISUAL_UNLOCK_CHECK = "ck_visual_catalog_items_ck_visual_catalog_items_unlock__8f86"


def _bind() -> Connection:
    return op.get_bind()


def _has_table(connection: Connection, table_name: str) -> bool:
    return sa.inspect(connection).has_table(table_name)


def _has_column(connection: Connection, table_name: str, column_name: str) -> bool:
    if not _has_table(connection, table_name):
        return False
    return column_name in {
        column["name"] for column in sa.inspect(connection).get_columns(table_name)
    }


def _has_constraint(connection: Connection, table_name: str, constraint_name: str) -> bool:
    return (
        connection.execute(
            sa.text(
                "SELECT 1 FROM pg_constraint "
                "WHERE conrelid = to_regclass(:table_name) AND conname = :constraint_name"
            ),
            {"table_name": table_name, "constraint_name": constraint_name},
        ).scalar()
        is not None
    )


def _has_check_by_definition(
    connection: Connection,
    table_name: str,
    definition_fragment: str,
) -> bool:
    definitions = connection.execute(
        sa.text(
            "SELECT pg_get_constraintdef(c.oid) FROM pg_constraint c "
            "WHERE c.conrelid = to_regclass(:table_name) AND c.contype = 'c'"
        ),
        {"table_name": table_name},
    ).scalars()
    return any(definition_fragment in (definition or "") for definition in definitions)


def _ensure_check(
    connection: Connection,
    table_name: str,
    constraint_name: str,
    condition: str,
    *,
    actual_name: str | None = None,
    definition_fragment: str | None = None,
) -> None:
    exists = (
        _has_check_by_definition(connection, table_name, definition_fragment)
        if definition_fragment is not None
        else _has_constraint(connection, table_name, actual_name or constraint_name)
    )
    if not exists:
        op.create_check_constraint(constraint_name, table_name, condition)


def _ensure_unique(
    connection: Connection,
    table_name: str,
    constraint_name: str,
    columns: list[str],
) -> None:
    if not _has_constraint(connection, table_name, constraint_name):
        op.create_unique_constraint(constraint_name, table_name, columns)


def _ensure_primary_key(
    connection: Connection,
    table_name: str,
    constraint_name: str,
    columns: list[str],
) -> None:
    if not _has_constraint(connection, table_name, constraint_name):
        op.create_primary_key(constraint_name, table_name, columns)


def _ensure_foreign_key(
    connection: Connection,
    constraint_name: str,
    source_table: str,
    referent_table: str,
    local_columns: list[str],
    remote_columns: list[str],
    *,
    ondelete: str | None = None,
) -> None:
    if not _has_constraint(connection, source_table, constraint_name):
        op.create_foreign_key(
            constraint_name,
            source_table,
            referent_table,
            local_columns,
            remote_columns,
            ondelete=ondelete,
        )


def _repair_sports() -> None:
    connection = _bind()

    op.add_column(
        "sports",
        sa.Column(
            "icon_key",
            sa.String(length=64),
            nullable=False,
            server_default="icon-app-escudo",
        ),
        if_not_exists=True,
    )

    op.add_column(
        "sports",
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        if_not_exists=True,
    )
    _ensure_check(
        connection,
        "sports",
        "sort_order_non_negative",
        "sort_order >= 0",
        actual_name="ck_sports_sort_order_non_negative",
    )


def _repair_sport_formats() -> None:
    connection = _bind()

    players_per_team_missing = not _has_column(connection, "sport_formats", "players_per_team")
    op.add_column(
        "sport_formats",
        sa.Column("players_per_team", sa.Integer(), nullable=False, server_default="5"),
        if_not_exists=True,
    )
    if players_per_team_missing:
        # Mesmo backfill da revisão z9: formatos existentes usam o team_size.
        op.execute("UPDATE sport_formats SET players_per_team = team_size")

    op.add_column(
        "sport_formats",
        sa.Column("period_count", sa.Integer(), nullable=False, server_default="1"),
        if_not_exists=True,
    )
    op.add_column(
        "sport_formats",
        sa.Column(
            "score_model",
            sa.String(length=20),
            nullable=False,
            server_default="sets_points",
        ),
        if_not_exists=True,
    )
    op.add_column(
        "sport_formats",
        sa.Column(
            "positions",
            sa.JSON(),
            nullable=False,
            server_default=sa.text("'[]'"),
        ),
        if_not_exists=True,
    )

    _ensure_check(
        connection,
        "sport_formats",
        "players_per_team_positive",
        "players_per_team > 0",
        actual_name="ck_sport_formats_players_per_team_positive",
    )
    _ensure_check(
        connection,
        "sport_formats",
        "period_count_positive",
        "period_count > 0",
        actual_name="ck_sport_formats_period_count_positive",
    )
    _ensure_check(
        connection,
        "sport_formats",
        "score_model_valid",
        "score_model IN ('sets_points', 'goals')",
        actual_name="ck_sport_formats_score_model_valid",
    )


def _repair_visual_catalog_items() -> None:
    connection = _bind()

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
        if_not_exists=True,
    )
    _ensure_primary_key(connection, "visual_catalog_items", "pk_visual_catalog_items", ["id"])
    _ensure_unique(
        connection,
        "visual_catalog_items",
        "uq_visual_catalog_items_key",
        ["key"],
    )
    _ensure_check(
        connection,
        "visual_catalog_items",
        "ck_visual_catalog_items_kind_valid",
        "kind IN ('icon', 'frame', 'accent', 'entry', 'emote', 'badge')",
        actual_name=VISUAL_KIND_CHECK,
    )
    _ensure_check(
        connection,
        "visual_catalog_items",
        "ck_visual_catalog_items_unlock_state_valid",
        "unlock_state IN ('free', 'xp', 'pass')",
        actual_name=VISUAL_UNLOCK_CHECK,
    )
    op.create_index(
        "ix_visual_catalog_items_kind_active",
        "visual_catalog_items",
        ["kind", "active"],
        if_not_exists=True,
    )


def _repair_user_visual_identity() -> None:
    connection = _bind()

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
        if_not_exists=True,
    )
    _ensure_primary_key(
        connection,
        "user_visual_identity",
        "pk_user_visual_identity",
        ["user_id"],
    )
    _ensure_foreign_key(
        connection,
        "fk_user_visual_identity_user_id_users",
        "user_visual_identity",
        "users",
        ["user_id"],
        ["id"],
        ondelete="CASCADE",
    )
    for slot in ("icon", "frame", "accent", "entry", "emote", "badge"):
        _ensure_foreign_key(
            connection,
            f"fk_user_visual_identity_{slot}_key_visual_catalog_items",
            "user_visual_identity",
            "visual_catalog_items",
            [f"{slot}_key"],
            ["key"],
            ondelete="RESTRICT",
        )


def _repair_user_visual_unlocks() -> None:
    connection = _bind()

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
        if_not_exists=True,
    )
    _ensure_primary_key(connection, "user_visual_unlocks", "pk_user_visual_unlocks", ["id"])
    _ensure_unique(
        connection,
        "user_visual_unlocks",
        "uq_user_visual_unlocks_user_item",
        ["user_id", "item_id"],
    )
    _ensure_foreign_key(
        connection,
        "fk_user_visual_unlocks_user_id_users",
        "user_visual_unlocks",
        "users",
        ["user_id"],
        ["id"],
        ondelete="CASCADE",
    )
    _ensure_foreign_key(
        connection,
        "fk_user_visual_unlocks_item_id_visual_catalog_items",
        "user_visual_unlocks",
        "visual_catalog_items",
        ["item_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_index(
        "ix_user_visual_unlocks_user",
        "user_visual_unlocks",
        ["user_id"],
        if_not_exists=True,
    )


def _seed_visual_catalog() -> None:
    connection = _bind()
    statement = sa.text(
        "INSERT INTO visual_catalog_items "
        "(id, key, kind, name, asset_ref, season, unlock_state, active) "
        "VALUES "
        "(:id, :key, :kind, :name, :asset_ref, :season, 'free', true) "
        "ON CONFLICT (key) DO NOTHING"
    )
    for key, kind, name, asset_ref, season in VISUAL_ITEMS:
        connection.execute(
            statement,
            {
                "id": uuid.uuid4(),
                "key": key,
                "kind": kind,
                "name": name,
                "asset_ref": asset_ref,
                "season": season,
            },
        )


def _seed_futevolei() -> None:
    connection = _bind()
    connection.execute(
        sa.text(
            "INSERT INTO sports (id, slug, name, icon_key, sort_order, active) "
            "VALUES (:id, 'futevolei', 'Futevôlei', "
            "'icon-sport-futevolei-3x3', 30, false) "
            "ON CONFLICT (slug) DO NOTHING"
        ),
        {"id": uuid.uuid4()},
    )
    connection.execute(
        sa.text(
            "INSERT INTO sport_formats ("
            "id, sport_id, slug, name, team_size, players_per_team, "
            "total_participants, play_minutes, break_minutes, duration_minutes, "
            "period_count, score_model, positions, version, active) "
            "SELECT :id, s.id, 'futevolei-3x3', 'Futevôlei 3x3', 3, 3, 6, "
            "45, 0, 45, 1, 'sets_points', CAST('[]' AS json), 1, true "
            "FROM sports s WHERE s.slug = 'futevolei' "
            "ON CONFLICT (slug, version) DO NOTHING"
        ),
        {"id": uuid.uuid4()},
    )


def upgrade() -> None:
    _repair_sports()
    _repair_sport_formats()
    _repair_visual_catalog_items()
    _repair_user_visual_identity()
    _repair_user_visual_unlocks()
    _seed_visual_catalog()
    _seed_futevolei()


def downgrade() -> None:
    """Reparo somente para frente; não remove objetos nem dados de ``z9``."""
