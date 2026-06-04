"""quests.contact_text and quests.verifier_text

Free-form display strings telling claimers who to coordinate with
(contact) and who signs off on completion (verifier). Distinct from
the existing verifier_user_ids allow-list, which the system uses for
permission gating; these are human-readable affordances.

Revision ID: 0005
Revises: 0004
Create Date: 2026-05-09
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0005"
down_revision: str | None = "0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("quests", sa.Column("contact_text", sa.String, nullable=True))
    op.add_column("quests", sa.Column("verifier_text", sa.String, nullable=True))


def downgrade() -> None:
    op.drop_column("quests", "verifier_text")
    op.drop_column("quests", "contact_text")
