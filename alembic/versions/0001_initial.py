"""initial schema

Revision ID: 0001
Revises:
Create Date: 2026-05-08

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    _create_users()
    _create_taxonomy()
    _create_quests()
    _create_quest_claims()
    _create_xp_transactions()
    _create_quest_boosts()
    _create_api_keys()
    _create_partial_indexes()


def downgrade() -> None:
    op.drop_table("api_keys")
    op.drop_table("quest_boosts")
    op.drop_table("xp_transactions")
    op.drop_table("quest_claims")
    op.drop_table("quests")
    op.drop_table("locations")
    op.drop_table("guilds")
    op.drop_table("users")


def _create_users() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.BigInteger, primary_key=True),
        sa.Column("wiki_username", sa.String(255), nullable=False, unique=True),
        sa.Column("wiki_user_id", sa.BigInteger, nullable=True, unique=True),
        sa.Column("discord_user_id", sa.String(64), nullable=True, unique=True),
        sa.Column("discord_username", sa.String(255), nullable=True),
        sa.Column("xp_balance", sa.Integer, nullable=False, server_default="0"),
        sa.Column("level", sa.Integer, nullable=False, server_default="1"),
        sa.Column("is_system", sa.Boolean, nullable=False, server_default=sa.text("false")),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("xp_balance >= 0", name="users_xp_balance_nonneg"),
    )


def _create_taxonomy() -> None:
    op.create_table(
        "guilds",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("slug", sa.String(64), nullable=False, unique=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("wiki_url", sa.String(512), nullable=True),
        sa.Column("description", sa.String, nullable=True),
    )
    op.create_table(
        "locations",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("slug", sa.String(64), nullable=False, unique=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("kind", sa.String(16), nullable=False),
        sa.Column("description", sa.String, nullable=True),
    )


def _create_quests() -> None:
    op.create_table(
        "quests",
        sa.Column("id", sa.BigInteger, primary_key=True),
        sa.Column("parent_quest_id", sa.BigInteger, sa.ForeignKey("quests.id"), nullable=True),
        sa.Column("depth", sa.Integer, nullable=False, server_default="0"),
        sa.Column("rollup_mode", sa.String(16), nullable=False, server_default="manual"),
        sa.Column("creator_user_id", sa.BigInteger, sa.ForeignKey("users.id"), nullable=True),
        sa.Column("creator_attribution", sa.String(255), nullable=True),
        sa.Column("guild_id", sa.Integer, sa.ForeignKey("guilds.id"), nullable=True),
        sa.Column("location_id", sa.Integer, sa.ForeignKey("locations.id"), nullable=True),
        sa.Column("title", sa.String(512), nullable=False),
        sa.Column("description", sa.String, nullable=False),
        sa.Column(
            "skills", sa.ARRAY(sa.String), nullable=False, server_default=sa.text("'{}'::text[]")
        ),
        sa.Column("xp", sa.Integer, nullable=False, server_default="0"),
        sa.Column("xp_source", sa.String(32), nullable=False, server_default="manual"),
        sa.Column("creator_bonus_xp", sa.Integer, nullable=False, server_default="0"),
        sa.Column("verifier_bonus_xp", sa.Integer, nullable=False, server_default="0"),
        sa.Column("posting_fee_charged", sa.Integer, nullable=False, server_default="0"),
        sa.Column("posting_fee_destination", sa.String(16), nullable=True),
        sa.Column("urgency", sa.String(16), nullable=False, server_default="normal"),
        sa.Column("due_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column("party_min", sa.Integer, nullable=False, server_default="1"),
        sa.Column("party_max", sa.Integer, nullable=True),
        sa.Column(
            "requires_verification",
            sa.Boolean,
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column(
            "verifier_user_ids",
            sa.ARRAY(sa.BigInteger),
            nullable=False,
            server_default=sa.text("'{}'::bigint[]"),
        ),
        sa.Column("status", sa.String(16), nullable=False, server_default="open"),
        sa.Column("paid_out_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("done_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("internal_notes", sa.String, nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.CheckConstraint(
            "(paid_out_at IS NULL) OR (status IN ('done','verified'))",
            name="quests_paid_out_implies_terminal",
        ),
        sa.CheckConstraint("depth >= 0 AND depth <= 3", name="quests_depth_in_range"),
    )
    op.create_index("ix_quests_status", "quests", ["status"])
    op.create_index("ix_quests_guild_id", "quests", ["guild_id"])
    op.create_index("ix_quests_location_id", "quests", ["location_id"])
    op.create_index("ix_quests_parent_quest_id", "quests", ["parent_quest_id"])


def _create_quest_claims() -> None:
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


def _create_xp_transactions() -> None:
    op.create_table(
        "xp_transactions",
        sa.Column("id", sa.BigInteger, primary_key=True),
        sa.Column("user_id", sa.BigInteger, sa.ForeignKey("users.id"), nullable=False),
        sa.Column("amount", sa.Integer, nullable=False),
        sa.Column("reason", sa.String(48), nullable=False),
        sa.Column("quest_id", sa.BigInteger, sa.ForeignKey("quests.id"), nullable=True),
        sa.Column("boost_id", sa.BigInteger, nullable=True),  # FK added after quest_boosts exists
        sa.Column("memo", sa.String, nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column("created_by_user_id", sa.BigInteger, sa.ForeignKey("users.id"), nullable=True),
    )
    op.create_index("ix_xp_transactions_user_created", "xp_transactions", ["user_id", "created_at"])
    op.create_index("ix_xp_transactions_quest_id", "xp_transactions", ["quest_id"])


def _create_quest_boosts() -> None:
    op.create_table(
        "quest_boosts",
        sa.Column("id", sa.BigInteger, primary_key=True),
        sa.Column("quest_id", sa.BigInteger, sa.ForeignKey("quests.id"), nullable=False),
        sa.Column("booster_user_id", sa.BigInteger, sa.ForeignKey("users.id"), nullable=False),
        sa.Column("amount", sa.Integer, nullable=False),
        sa.Column("is_self_boost", sa.Boolean, nullable=False),
        sa.Column(
            "spend_txn_id", sa.BigInteger, sa.ForeignKey("xp_transactions.id"), nullable=False
        ),
        sa.Column(
            "refund_txn_id", sa.BigInteger, sa.ForeignKey("xp_transactions.id"), nullable=True
        ),
        sa.Column("refunded_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.CheckConstraint("amount > 0", name="quest_boosts_amount_positive"),
    )
    op.create_index("ix_quest_boosts_quest_id", "quest_boosts", ["quest_id"])
    op.create_foreign_key(
        "fk_xp_transactions_boost_id",
        "xp_transactions",
        "quest_boosts",
        ["boost_id"],
        ["id"],
    )


def _create_api_keys() -> None:
    op.create_table(
        "api_keys",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("name", sa.String(128), nullable=False),
        sa.Column("key_hash", sa.String(255), nullable=False),
        sa.Column("scopes", sa.ARRAY(sa.String), nullable=False, server_default=sa.text("'{}'::text[]")),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
    )


def _create_partial_indexes() -> None:
    """Indexes that need WHERE clauses, not expressible cleanly via SQLAlchemy column defs."""
    op.create_index(
        "ix_quests_due_open",
        "quests",
        ["due_date"],
        postgresql_where=sa.text("status IN ('open','claimed')"),
    )
    op.create_index(
        "ix_quest_boosts_active",
        "quest_boosts",
        ["quest_id"],
        postgresql_where=sa.text("refunded_at IS NULL"),
    )
    op.create_index(
        "users_one_welcome_grant",
        "xp_transactions",
        ["user_id"],
        unique=True,
        postgresql_where=sa.text("reason = 'welcome_grant'"),
    )
