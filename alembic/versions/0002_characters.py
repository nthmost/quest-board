"""characters as primary actor

Adds character_classes, characters, npc_quest_givers. Migrates existing
actor columns from user_id to character_id on quest_claims, quest_boosts,
and xp_transactions. Adds creator_character_id and creator_npc_id to
quests. Drops xp_balance and level from users.

Test data is wiped because the existing rows on quest_claims / quests /
xp_transactions reference user_id values that have no character_id
counterpart yet. This migration assumes the system has no production
data — accurate at the time it was authored. If you ever need to run
this against real data, write a backfill that creates a Character per
existing user first and rewires the FK columns.

Revision ID: 0002
Revises: 0001
Create Date: 2026-05-09
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    _wipe_test_data()
    _create_character_classes()
    _create_characters()
    _create_npc_quest_givers()
    _add_quest_creator_columns()
    _migrate_quest_claims()
    _migrate_quest_boosts()
    _migrate_xp_transactions()
    _drop_user_economy_columns()
    _seed_character_classes()


def downgrade() -> None:
    _restore_user_economy_columns()
    _restore_xp_transactions_user_id()
    _restore_quest_boosts_user_id()
    _restore_quest_claims_user_id()
    _drop_quest_creator_columns()
    op.drop_table("npc_quest_givers")
    op.drop_table("characters")
    op.drop_table("character_classes")


# ─── upgrade helpers ──────────────────────────────────────────────────────────

def _wipe_test_data() -> None:
    """Drop rows that reference user_id as actor — they don't survive the migration."""
    op.execute("DELETE FROM xp_transactions")
    op.execute("DELETE FROM quest_boosts")
    op.execute("DELETE FROM quest_claims")
    op.execute("DELETE FROM quests")


def _create_character_classes() -> None:
    op.create_table(
        "character_classes",
        sa.Column("slug", sa.String(32), primary_key=True),
        sa.Column("name", sa.String(64), nullable=False),
        sa.Column("description", sa.String, nullable=False),
        sa.Column("guild_affinity", sa.JSON, nullable=False, server_default=sa.text("'{}'::json")),
        sa.Column("flavor_kit_slug", sa.String(32), nullable=True),
    )


def _create_characters() -> None:
    op.create_table(
        "characters",
        sa.Column("id", sa.BigInteger, primary_key=True),
        sa.Column("user_id", sa.BigInteger, sa.ForeignKey("users.id"), nullable=False),
        sa.Column("name", sa.String(64), nullable=False),
        sa.Column(
            "class_slug",
            sa.String(32),
            sa.ForeignKey("character_classes.slug"),
            nullable=False,
        ),
        sa.Column("primary_guild_id", sa.Integer, sa.ForeignKey("guilds.id"), nullable=True),
        sa.Column("xp_balance", sa.Integer, nullable=False, server_default="0"),
        sa.Column("level", sa.Integer, nullable=False, server_default="1"),
        sa.Column("flavor_seed", sa.Integer, nullable=False, server_default="0"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("xp_balance >= 0", name="characters_xp_balance_nonneg"),
        sa.UniqueConstraint("user_id", "name", name="characters_unique_name_per_user"),
    )
    op.create_index("ix_characters_user_id", "characters", ["user_id"])


def _create_npc_quest_givers() -> None:
    op.create_table(
        "npc_quest_givers",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("handle", sa.String(64), nullable=False, unique=True),
        sa.Column("display_name", sa.String(128), nullable=False),
        sa.Column("guild_id", sa.Integer, sa.ForeignKey("guilds.id"), nullable=True),
        sa.Column("post_cadence_sec", sa.Integer, nullable=False),
        sa.Column("description", sa.String, nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )


def _add_quest_creator_columns() -> None:
    op.add_column(
        "quests",
        sa.Column(
            "creator_character_id",
            sa.BigInteger,
            sa.ForeignKey("characters.id"),
            nullable=True,
        ),
    )
    op.add_column(
        "quests",
        sa.Column(
            "creator_npc_id",
            sa.Integer,
            sa.ForeignKey("npc_quest_givers.id"),
            nullable=True,
        ),
    )
    op.create_index("ix_quests_creator_character_id", "quests", ["creator_character_id"])


def _migrate_quest_claims() -> None:
    """Rebuild quest_claims with character_id instead of user_id."""
    op.drop_table("quest_claims")
    op.create_table(
        "quest_claims",
        sa.Column("quest_id", sa.BigInteger, sa.ForeignKey("quests.id"), primary_key=True),
        sa.Column(
            "character_id",
            sa.BigInteger,
            sa.ForeignKey("characters.id"),
            primary_key=True,
        ),
        sa.Column(
            "claimed_at",
            sa.DateTime(timezone=True),
            primary_key=True,
            server_default=sa.func.now(),
        ),
        sa.Column("released_at", sa.DateTime(timezone=True), nullable=True),
    )


def _migrate_quest_boosts() -> None:
    """Swap booster_user_id → booster_character_id."""
    op.drop_constraint("quest_boosts_booster_user_id_fkey", "quest_boosts", type_="foreignkey")
    op.drop_column("quest_boosts", "booster_user_id")
    op.add_column(
        "quest_boosts",
        sa.Column(
            "booster_character_id",
            sa.BigInteger,
            sa.ForeignKey("characters.id"),
            nullable=False,
        ),
    )


def _migrate_xp_transactions() -> None:
    """Swap user_id → character_id and fix the partial unique index."""
    op.drop_index("users_one_welcome_grant", table_name="xp_transactions")
    op.drop_index("ix_xp_transactions_user_created", table_name="xp_transactions")
    op.drop_constraint(
        "xp_transactions_user_id_fkey", "xp_transactions", type_="foreignkey"
    )
    op.drop_column("xp_transactions", "user_id")
    op.add_column(
        "xp_transactions",
        sa.Column(
            "character_id",
            sa.BigInteger,
            sa.ForeignKey("characters.id"),
            nullable=False,
        ),
    )
    op.create_index(
        "ix_xp_transactions_character_created",
        "xp_transactions",
        ["character_id", "created_at"],
    )
    op.create_index(
        "characters_one_welcome_grant",
        "xp_transactions",
        ["character_id"],
        unique=True,
        postgresql_where=sa.text("reason = 'welcome_grant'"),
    )


def _drop_user_economy_columns() -> None:
    op.drop_constraint("users_xp_balance_nonneg", "users", type_="check")
    op.drop_column("users", "xp_balance")
    op.drop_column("users", "level")


def _seed_character_classes() -> None:
    """Seed the eight Progress-Quest-flavored archetypes from DEMO.md §4."""
    # NB: 'quartermaster' was removed in 0004 — reserved as the system voice
    # for quests with no concrete creator. Don't re-add it as a player class.
    classes = [
        ("hacker",       "Hacker",       "Will compile from source on principle."),
        ("mechanic",     "Mechanic",     "Has Loctite in their backpack."),
        ("bard",         "Bard",         "Owns a soldering iron mostly because it's pretty."),
        ("sysadmin",     "Sysadmin",     "Speaks in incident-report tense."),
        ("bio-tinkerer", "Bio-Tinkerer", "Asks questions about the autoclave."),
        ("custodian",    "Custodian",   "Has Strong Opinions about the dish rack."),
        ("scribe",       "Scribe",      "Won't let a wiki page rot on their watch."),
    ]
    op.bulk_insert(
        sa.table(
            "character_classes",
            sa.Column("slug", sa.String),
            sa.Column("name", sa.String),
            sa.Column("description", sa.String),
        ),
        [{"slug": s, "name": n, "description": d} for s, n, d in classes],
    )


# ─── downgrade helpers (best-effort; data is gone) ─────────────────────────────

def _restore_user_economy_columns() -> None:
    op.add_column("users", sa.Column("xp_balance", sa.Integer, server_default="0", nullable=False))
    op.add_column("users", sa.Column("level", sa.Integer, server_default="1", nullable=False))
    op.create_check_constraint("users_xp_balance_nonneg", "users", "xp_balance >= 0")


def _restore_xp_transactions_user_id() -> None:
    op.drop_index("characters_one_welcome_grant", table_name="xp_transactions")
    op.drop_index("ix_xp_transactions_character_created", table_name="xp_transactions")
    op.drop_constraint(
        "xp_transactions_character_id_fkey", "xp_transactions", type_="foreignkey",
    )
    op.drop_column("xp_transactions", "character_id")
    op.add_column(
        "xp_transactions",
        sa.Column("user_id", sa.BigInteger, sa.ForeignKey("users.id"), nullable=False),
    )
    op.create_index("ix_xp_transactions_user_created", "xp_transactions", ["user_id", "created_at"])
    op.create_index(
        "users_one_welcome_grant",
        "xp_transactions",
        ["user_id"],
        unique=True,
        postgresql_where=sa.text("reason = 'welcome_grant'"),
    )


def _restore_quest_boosts_user_id() -> None:
    op.drop_constraint(
        "quest_boosts_booster_character_id_fkey", "quest_boosts", type_="foreignkey",
    )
    op.drop_column("quest_boosts", "booster_character_id")
    op.add_column(
        "quest_boosts",
        sa.Column(
            "booster_user_id", sa.BigInteger, sa.ForeignKey("users.id"), nullable=False,
        ),
    )


def _restore_quest_claims_user_id() -> None:
    op.drop_table("quest_claims")
    op.create_table(
        "quest_claims",
        sa.Column("quest_id", sa.BigInteger, sa.ForeignKey("quests.id"), primary_key=True),
        sa.Column("user_id", sa.BigInteger, sa.ForeignKey("users.id"), primary_key=True),
        sa.Column(
            "claimed_at",
            sa.DateTime(timezone=True),
            primary_key=True,
            server_default=sa.func.now(),
        ),
        sa.Column("released_at", sa.DateTime(timezone=True), nullable=True),
    )


def _drop_quest_creator_columns() -> None:
    op.drop_index("ix_quests_creator_character_id", table_name="quests")
    op.drop_column("quests", "creator_npc_id")
    op.drop_column("quests", "creator_character_id")
