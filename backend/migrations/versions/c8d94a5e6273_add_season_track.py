"""add season track, badges and player items

Revision ID: c8d94a5e6273
Revises: b7c8394d5162
Create Date: 2026-11-12 17:00:00.000000

"""

import uuid
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c8d94a5e6273"
down_revision: str | Sequence[str] | None = "b7c8394d5162"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

XP_PER_LEVEL = 150
TRACK_ITEMS = (
    (4, "q4_emote_joinha", "Emote Joinha", "emote", "free"),
    (8, "q4_headband", "Faixa de Cabeça", "accessory", "free"),
    (12, "q4_entry_bolt", "Ícone Relâmpago", "entry_icon", "pass"),
    (17, "q4_emote_clap", "Emote Palmas", "emote", "free"),
    (21, "q4_lobby_smoke", "Entrada Fumaça", "lobby_animation", "pass"),
    (26, "q4_glasses", "Óculos Escuros", "accessory", "pass"),
    (30, "q4_badge_season", "Insígnia da Temporada", "badge", "free"),
)
FREE_TICKET_LEVELS = (5, 10, 15, 20, 25, 30)


def upgrade() -> None:
    """Cria catálogo de itens, trilha, recompensas e insígnias."""
    op.create_table(
        "season_items",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("season_id", sa.Uuid(), nullable=True),
        sa.Column("code", sa.String(length=40), nullable=False),
        sa.Column("name", sa.String(length=60), nullable=False),
        sa.Column("category", sa.String(length=20), nullable=False),
        sa.Column("artwork_ref", sa.String(length=120), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "category IN ('accessory','emote','lobby_animation','entry_icon','badge')",
            name="category_valid",
        ),
        sa.ForeignKeyConstraint(["season_id"], ["seasons.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code"),
    )

    op.create_table(
        "season_track_levels",
        sa.Column("season_id", sa.Uuid(), nullable=False),
        sa.Column("level", sa.SmallInteger(), nullable=False),
        sa.Column("xp_required", sa.Integer(), nullable=False),
        sa.Column("item_code", sa.String(length=40), nullable=True),
        sa.Column("free_tickets", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column(
            "track", sa.String(length=6), server_default=sa.text("'free'"), nullable=False
        ),
        sa.CheckConstraint("level BETWEEN 1 AND 30", name="level_valid"),
        sa.CheckConstraint("xp_required >= 0", name="xp_non_negative"),
        sa.CheckConstraint("free_tickets >= 0", name="tickets_non_negative"),
        sa.CheckConstraint("track IN ('free', 'pass')", name="track_valid"),
        sa.ForeignKeyConstraint(["season_id"], ["seasons.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("season_id", "level"),
    )

    op.create_table(
        "season_claims",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("season_id", sa.Uuid(), nullable=False),
        sa.Column("level", sa.SmallInteger(), nullable=False),
        sa.Column(
            "claimed_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint("level BETWEEN 1 AND 30", name="level_valid"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["season_id"], ["seasons.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("user_id", "season_id", "level"),
    )

    op.create_table(
        "badges",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("code", sa.String(length=40), nullable=False),
        sa.Column("name", sa.String(length=60), nullable=False),
        sa.Column("kind", sa.String(length=10), nullable=False),
        sa.Column("season_id", sa.Uuid(), nullable=True),
        sa.Column("artwork_ref", sa.String(length=120), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint("kind IN ('season', 'founder', 'medal')", name="kind_valid"),
        sa.ForeignKeyConstraint(["season_id"], ["seasons.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code"),
    )

    op.create_table(
        "player_badges",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("badge_id", sa.Uuid(), nullable=False),
        sa.Column("equipped_slot", sa.SmallInteger(), nullable=True),
        sa.Column(
            "awarded_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "equipped_slot IS NULL OR equipped_slot BETWEEN 1 AND 3", name="slot_valid"
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["badge_id"], ["badges.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "badge_id", name="uq_player_badges_user_badge"),
    )
    op.create_index(
        "uq_player_badges_user_slot",
        "player_badges",
        ["user_id", "equipped_slot"],
        unique=True,
        postgresql_where=sa.text("equipped_slot IS NOT NULL"),
    )

    op.create_table(
        "player_items",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("item_code", sa.String(length=40), nullable=False),
        sa.Column("season_id", sa.Uuid(), nullable=True),
        sa.Column(
            "awarded_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["season_id"], ["seasons.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "item_code", name="uq_player_items"),
    )

    connection = op.get_bind()
    season_row = connection.execute(
        sa.text("SELECT id, code FROM seasons WHERE code = '2026-Q4'")
    ).first()
    if season_row is None:
        return
    season_id, season_code = season_row

    op.bulk_insert(
        sa.table(
            "season_items",
            sa.column("id", sa.Uuid()),
            sa.column("season_id", sa.Uuid()),
            sa.column("code", sa.String()),
            sa.column("name", sa.String()),
            sa.column("category", sa.String()),
            sa.column("artwork_ref", sa.String()),
        ),
        [
            {
                "id": uuid.uuid4(),
                "season_id": season_id,
                "code": code,
                "name": name,
                "category": category,
                "artwork_ref": f"placeholder/{code}",
            }
            for _level, code, name, category, _track in TRACK_ITEMS
        ],
    )

    badge_code = f"season_{season_code.lower().replace('-', '_')}"
    op.bulk_insert(
        sa.table(
            "badges",
            sa.column("id", sa.Uuid()),
            sa.column("code", sa.String()),
            sa.column("name", sa.String()),
            sa.column("kind", sa.String()),
            sa.column("season_id", sa.Uuid()),
            sa.column("artwork_ref", sa.String()),
        ),
        [
            {
                "id": uuid.uuid4(),
                "code": badge_code,
                "name": f"Temporada {season_code}",
                "kind": "season",
                "season_id": season_id,
                "artwork_ref": f"placeholder/{badge_code}",
            }
        ],
    )

    items_by_level = {level: (code, track) for level, code, _n, _c, track in TRACK_ITEMS}
    op.bulk_insert(
        sa.table(
            "season_track_levels",
            sa.column("season_id", sa.Uuid()),
            sa.column("level", sa.SmallInteger()),
            sa.column("xp_required", sa.Integer()),
            sa.column("item_code", sa.String()),
            sa.column("free_tickets", sa.Integer()),
            sa.column("track", sa.String()),
        ),
        [
            {
                "season_id": season_id,
                "level": level,
                "xp_required": level * XP_PER_LEVEL,
                "item_code": items_by_level.get(level, (None, "free"))[0],
                "free_tickets": 1 if level in FREE_TICKET_LEVELS else 0,
                "track": items_by_level.get(level, (None, "free"))[1],
            }
            for level in range(1, 31)
        ],
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table("player_items")
    op.drop_index("uq_player_badges_user_slot", table_name="player_badges")
    op.drop_table("player_badges")
    op.drop_table("badges")
    op.drop_table("season_claims")
    op.drop_table("season_track_levels")
    op.drop_table("season_items")
