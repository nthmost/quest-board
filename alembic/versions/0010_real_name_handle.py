"""Add real_name + show_real_name to users (real name / handle identity model).

The handle (stored as `wiki_username`) is the public name; real_name is private
by default. Backfill real_name from the existing handle so no row is blank, and
default show_real_name to false (pseudonymous).

Revision ID: 0010
Revises: 0009
"""

from alembic import op
import sqlalchemy as sa

revision = "0010"
down_revision = "0009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("real_name", sa.String(length=255), nullable=True),
    )
    op.add_column(
        "users",
        sa.Column(
            "show_real_name",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )
    # Backfill: existing accounts get real_name seeded from their handle so the
    # field is never empty for people who signed up before it existed.
    op.execute(
        "UPDATE users SET real_name = wiki_username WHERE real_name IS NULL"
    )


def downgrade() -> None:
    op.drop_column("users", "show_real_name")
    op.drop_column("users", "real_name")
