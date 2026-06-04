"""User model: pure identity. Economy lives on Character."""

from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    wiki_username: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    wiki_user_id: Mapped[int | None] = mapped_column(BigInteger, unique=True, nullable=True)
    discord_user_id: Mapped[str | None] = mapped_column(String(64), unique=True, nullable=True)
    discord_username: Mapped[str | None] = mapped_column(String(255), nullable=True)
    is_system: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )
    active_character_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("characters.id"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
