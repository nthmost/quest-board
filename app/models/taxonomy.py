"""Guilds and Locations: enumerated, admin-curated taxonomies."""

from sqlalchemy import Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class Guild(Base):
    __tablename__ = "guilds"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    slug: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    wiki_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    description: Mapped[str | None] = mapped_column(String, nullable=True)


class Location(Base):
    __tablename__ = "locations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    slug: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    kind: Mapped[str] = mapped_column(String(16), nullable=False)  # 'physical' | 'online'
    description: Mapped[str | None] = mapped_column(String, nullable=True)
