"""Add spaces (makerspaces) + user.primary_space_id + quest.space_id, seed founding spaces.

The board spans multiple member sites. Users pick a primary space; quests can
be scoped to a space.

Revision ID: 0009
Revises: 0008
"""

from alembic import op
import sqlalchemy as sa

revision = "0009"
down_revision = "0008"
branch_labels = None
depends_on = None


FOUNDING_SPACES = [
    # slug, name, neighborhood, url, description, sort_order
    ("noisebridge", "Noisebridge", "Mission, San Francisco", "https://www.noisebridge.net",
     "Free, member-run hackerspace in the Mission — the lead site.", 10),
    ("sequoia-fabrica", "Sequoia Fabrica", "Potrero Hill, San Francisco", "https://sequoiafabrica.org",
     "Intergenerational community makerspace in Potrero Hill.", 20),
    ("opencircuit-sf", "OpenCircuit SF", "Citywide, San Francisco", "http://opencircuitsf.com",
     "Hands-on electronics and fabrication workshops across the city.", 30),
    ("sudo-room", "Sudo Room", "Oakland", "https://sudoroom.org",
     "Community hackerspace at Omni Commons in Oakland.", 40),
]


def upgrade() -> None:
    op.create_table(
        "spaces",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("slug", sa.String(length=64), nullable=False, unique=True),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("neighborhood", sa.String(length=128), nullable=True),
        sa.Column("url", sa.String(length=512), nullable=True),
        sa.Column("description", sa.String(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
    )

    op.add_column(
        "users",
        sa.Column("primary_space_id", sa.Integer(), sa.ForeignKey("spaces.id"), nullable=True),
    )
    op.add_column(
        "quests",
        sa.Column("space_id", sa.Integer(), sa.ForeignKey("spaces.id"), nullable=True),
    )
    op.create_index("ix_quests_space_id", "quests", ["space_id"])

    spaces = sa.table(
        "spaces",
        sa.column("slug", sa.String),
        sa.column("name", sa.String),
        sa.column("neighborhood", sa.String),
        sa.column("url", sa.String),
        sa.column("description", sa.String),
        sa.column("sort_order", sa.Integer),
    )
    op.bulk_insert(
        spaces,
        [
            {
                "slug": s, "name": n, "neighborhood": hood,
                "url": url, "description": desc, "sort_order": order,
            }
            for (s, n, hood, url, desc, order) in FOUNDING_SPACES
        ],
    )


def downgrade() -> None:
    op.drop_index("ix_quests_space_id", table_name="quests")
    op.drop_column("quests", "space_id")
    op.drop_column("users", "primary_space_id")
    op.drop_table("spaces")
