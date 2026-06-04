"""CharacterClass: the eight Progress-Quest-flavored archetypes from DEMO.md §4."""

from sqlalchemy import JSON, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class CharacterClass(Base):
    __tablename__ = "character_classes"

    slug: Mapped[str] = mapped_column(String(32), primary_key=True)
    name: Mapped[str] = mapped_column(String(64), nullable=False)
    description: Mapped[str] = mapped_column(String, nullable=False)
    guild_affinity: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    flavor_kit_slug: Mapped[str | None] = mapped_column(String(32), nullable=True)
