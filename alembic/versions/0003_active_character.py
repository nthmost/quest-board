"""users.active_character_id

Adds a nullable FK on users pointing at the user's currently-selected
character. Single source of truth so the front page knows which sheet
to render and the /me/characters page knows which card to mark.

Revision ID: 0003
Revises: 0002
Create Date: 2026-05-09
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column(
            "active_character_id",
            sa.BigInteger,
            sa.ForeignKey("characters.id"),
            nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_constraint(
        "users_active_character_id_fkey", "users", type_="foreignkey",
    )
    op.drop_column("users", "active_character_id")
