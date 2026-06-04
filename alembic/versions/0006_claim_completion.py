"""Add completion columns to quest_claims.

Revision ID: 0006
Revises: 0005
Create Date: 2026-05-27
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0006"
down_revision: str | None = "0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("quest_claims", sa.Column("done_state", sa.Text, nullable=True))
    op.add_column("quest_claims", sa.Column("claim_notes", sa.Text, nullable=True))
    op.add_column("quest_claims", sa.Column("time_spent_minutes", sa.Integer, nullable=True))
    op.add_column(
        "quest_claims",
        sa.Column("reported_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_check_constraint(
        "quest_claims_time_nonneg",
        "quest_claims",
        "time_spent_minutes IS NULL OR time_spent_minutes >= 0",
    )


def downgrade() -> None:
    op.drop_constraint("quest_claims_time_nonneg", "quest_claims", type_="check")
    op.drop_column("quest_claims", "reported_at")
    op.drop_column("quest_claims", "time_spent_minutes")
    op.drop_column("quest_claims", "claim_notes")
    op.drop_column("quest_claims", "done_state")
