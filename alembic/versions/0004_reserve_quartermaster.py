"""reserve Quartermaster as system voice

Pulls 'quartermaster' out of the player-class roster so it can serve
as the default attribution for quests with no concrete creator. Any
characters that were Quartermasters are migrated to 'custodian' as
the nearest fit, then the row is dropped from character_classes.

Revision ID: 0004
Revises: 0003
Create Date: 2026-05-09
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0004"
down_revision: str | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        "UPDATE characters SET class_slug = 'custodian' "
        "WHERE class_slug = 'quartermaster'"
    )
    op.execute("DELETE FROM character_classes WHERE slug = 'quartermaster'")


def downgrade() -> None:
    op.execute(
        "INSERT INTO character_classes (slug, name, description) "
        "VALUES ('quartermaster', 'Quartermaster', "
        "'Knows where the spare M3 bolts are.')"
    )
    # No way to know which custodians used to be quartermasters; leave them.
