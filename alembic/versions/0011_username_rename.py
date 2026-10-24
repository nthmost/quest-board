"""Rename users.wiki_username -> users.username; drop unused users.wiki_user_id.

The login credential is just a username now. Drop the leftover MediaWiki
internal-id column, which was never used by the application.

Revision ID: 0011
Revises: 0010
"""

from alembic import op
import sqlalchemy as sa

revision = "0011"
down_revision = "0010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column("users", "wiki_username", new_column_name="username")
    op.drop_column("users", "wiki_user_id")


def downgrade() -> None:
    op.add_column(
        "users",
        sa.Column("wiki_user_id", sa.BigInteger(), nullable=True),
    )
    op.create_unique_constraint("users_wiki_user_id_key", "users", ["wiki_user_id"])
    op.alter_column("users", "username", new_column_name="wiki_username")
