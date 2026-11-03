"""add profile, availability, region and venues

Revision ID: b8d2f4a6c910
Revises: a7c3e9f2b415
Create Date: 2026-11-03 00:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "b8d2f4a6c910"
down_revision: str | Sequence[str] | None = "a7c3e9f2b415"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Cria catálogo, perfil, disponibilidade, região e locais."""
    op.create_table(
        "sports",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("slug", sa.String(length=40), nullable=False),
        sa.Column("name", sa.String(length=80), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name="pk_sports"),
        sa.UniqueConstraint("slug", name="uq_sports_slug"),
    )

    op.create_table(
        "sport_formats",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("sport_id", sa.Uuid(), nullable=False),
        sa.Column("slug", sa.String(length=40), nullable=False),
        sa.Column("name", sa.String(length=80), nullable=False),
        sa.Column("team_size", sa.Integer(), nullable=False),
        sa.Column("total_participants", sa.Integer(), nullable=False),
        sa.Column("play_minutes", sa.Integer(), nullable=False),
        sa.Column("break_minutes", sa.Integer(), nullable=False),
        sa.Column("duration_minutes", sa.Integer(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint("team_size > 0", name="team_size_positive"),
        sa.CheckConstraint(
            "total_participants = team_size * 2",
            name="participants_match_teams",
        ),
        sa.CheckConstraint("play_minutes > 0", name="play_minutes_positive"),
        sa.CheckConstraint("break_minutes >= 0", name="break_minutes_non_negative"),
        sa.CheckConstraint(
            "duration_minutes = play_minutes + break_minutes",
            name="duration_matches_parts",
        ),
        sa.ForeignKeyConstraint(
            ["sport_id"],
            ["sports.id"],
            name="fk_sport_formats_sport_id_sports",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_sport_formats"),
        sa.UniqueConstraint("slug", "version", name="uq_sport_formats_slug_version"),
    )
    op.create_index("ix_sport_formats_sport_id", "sport_formats", ["sport_id"])

    op.create_table(
        "user_profiles",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("display_name", sa.String(length=60), nullable=True),
        sa.Column("bio", sa.String(length=280), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name="fk_user_profiles_user_id_users",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("user_id", name="pk_user_profiles"),
    )

    op.create_table(
        "user_sport_profiles",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("format_id", sa.Uuid(), nullable=False),
        sa.Column("level", sa.String(length=20), nullable=False),
        sa.Column("court_preference", sa.String(length=20), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "level IN ('beginner', 'intermediate', 'advanced')",
            name="level_valid",
        ),
        sa.CheckConstraint(
            "court_preference IN ('PUBLIC_ONLY', 'PRIVATE_ONLY', 'ANY')",
            name="court_preference_valid",
        ),
        sa.ForeignKeyConstraint(
            ["format_id"],
            ["sport_formats.id"],
            name="fk_user_sport_profiles_format_id_sport_formats",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name="fk_user_sport_profiles_user_id_users",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_user_sport_profiles"),
        sa.UniqueConstraint(
            "user_id",
            "format_id",
            name="uq_user_sport_profiles_user_format",
        ),
    )
    op.create_index(
        "ix_user_sport_profiles_user_id",
        "user_sport_profiles",
        ["user_id"],
    )
    op.create_index(
        "ix_user_sport_profiles_format_id",
        "user_sport_profiles",
        ["format_id"],
    )

    op.create_table(
        "availabilities",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("weekday", sa.SmallInteger(), nullable=False),
        sa.Column("start_time", sa.Time(), nullable=False),
        sa.Column("end_time", sa.Time(), nullable=False),
        sa.Column("timezone", sa.String(length=64), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint("weekday BETWEEN 1 AND 7", name="weekday_valid"),
        sa.CheckConstraint("start_time < end_time", name="time_order_valid"),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name="fk_availabilities_user_id_users",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_availabilities"),
        sa.UniqueConstraint(
            "user_id",
            "weekday",
            "start_time",
            "end_time",
            name="uq_availability_window",
        ),
    )
    op.create_index(
        "ix_availabilities_user_weekday",
        "availabilities",
        ["user_id", "weekday"],
    )

    op.create_table(
        "user_regions",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("source", sa.String(length=10), nullable=False),
        sa.Column("cep", sa.String(length=8), nullable=True),
        sa.Column("city", sa.String(length=120), nullable=True),
        sa.Column("state", sa.String(length=2), nullable=True),
        sa.Column("radius_km", sa.Integer(), nullable=False),
        sa.Column("center_lat", sa.Float(), nullable=False),
        sa.Column("center_lng", sa.Float(), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint("source IN ('gps', 'cep')", name="source_valid"),
        sa.CheckConstraint("radius_km BETWEEN 1 AND 200", name="radius_valid"),
        sa.CheckConstraint("center_lat BETWEEN -90 AND 90", name="lat_valid"),
        sa.CheckConstraint("center_lng BETWEEN -180 AND 180", name="lng_valid"),
        sa.CheckConstraint(
            "source = 'gps' OR (cep IS NOT NULL AND city IS NOT NULL AND state IS NOT NULL)",
            name="cep_fields_required",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name="fk_user_regions_user_id_users",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("user_id", name="pk_user_regions"),
    )

    op.create_table(
        "venues",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("kind", sa.String(length=20), nullable=False),
        sa.Column("city", sa.String(length=120), nullable=False),
        sa.Column("state", sa.String(length=2), nullable=False),
        sa.Column("cep", sa.String(length=8), nullable=True),
        sa.Column("address", sa.String(length=200), nullable=True),
        sa.Column("lat", sa.Float(), nullable=False),
        sa.Column("lng", sa.Float(), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint("kind IN ('public', 'private')", name="kind_valid"),
        sa.CheckConstraint("lat BETWEEN -90 AND 90", name="lat_valid"),
        sa.CheckConstraint("lng BETWEEN -180 AND 180", name="lng_valid"),
        sa.PrimaryKeyConstraint("id", name="pk_venues"),
    )
    op.create_index("ix_venues_city_state", "venues", ["city", "state"])

    if op.get_context().dialect.name == "postgresql":
        op.execute(
            "CREATE INDEX ix_venues_location_gist ON venues "
            "USING GIST (ST_SetSRID(ST_MakePoint(lng, lat), 4326))"
        )

    op.execute(
        sa.text(
            """
            INSERT INTO sports (id, slug, name, active) VALUES
              ('11111111-1111-4111-8111-111111111111', 'futebol', 'Futebol', true),
              ('22222222-2222-4222-8222-222222222222', 'volei', 'Vôlei', true)
            """
        )
    )
    op.execute(
        sa.text(
            """
            INSERT INTO sport_formats
              (id, sport_id, slug, name, team_size, total_participants,
               play_minutes, break_minutes, duration_minutes, version, active)
            VALUES
              ('33333333-3333-4333-8333-333333333333',
               '11111111-1111-4111-8111-111111111111',
               'futebol-5x5', 'Futebol 5x5', 5, 10, 50, 10, 60, 1, true),
              ('44444444-4444-4444-8444-444444444444',
               '22222222-2222-4222-8222-222222222222',
               'volei-6x6', 'Vôlei 6x6', 6, 12, 60, 0, 60, 1, true)
            """
        )
    )


def downgrade() -> None:
    """Remove catálogo, perfil, disponibilidade, região e locais."""
    if op.get_context().dialect.name == "postgresql":
        op.execute("DROP INDEX IF EXISTS ix_venues_location_gist")
    op.drop_table("venues")
    op.drop_table("user_regions")
    op.drop_table("availabilities")
    op.drop_table("user_sport_profiles")
    op.drop_table("user_profiles")
    op.drop_table("sport_formats")
    op.drop_table("sports")
