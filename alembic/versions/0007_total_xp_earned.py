"""Add total_xp_earned to characters (lifetime XP; determines level).

xp_balance = spendable pool (can decrease via posting fee)
total_xp_earned = monotonically increasing; drives level calculation

Revision ID: 0007
Revises: 0006
"""

from alembic import op
import sqlalchemy as sa

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "characters",
        sa.Column("total_xp_earned", sa.Integer(), nullable=False, server_default="0"),
    )
    op.execute("""
        UPDATE characters c
        SET total_xp_earned = COALESCE((
            SELECT SUM(amount)
            FROM xp_transactions
            WHERE character_id = c.id AND amount > 0
        ), 0)
    """)


def downgrade() -> None:
    op.drop_column("characters", "total_xp_earned")
