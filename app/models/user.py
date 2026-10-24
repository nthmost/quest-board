"""User model: pure identity. Economy lives on Character."""

from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    # Login username: the credential they sign in with, fixed, never shown to others.
    username: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    # Real name: collected at signup (required there) but unenforced/unverified
    # and private by default. Nullable in the DB for system rows.
    real_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    # When true, the real name is shown alongside the visible name to everyone,
    # as "Visible Name (Real Name)". Off by default — pseudonymous.
    show_real_name: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )
    # Argon2id hash for login. Null for system rows with no password set.
    password_hash: Mapped[str | None] = mapped_column(String(255), nullable=True)
    discord_user_id: Mapped[str | None] = mapped_column(String(64), unique=True, nullable=True)
    discord_username: Mapped[str | None] = mapped_column(String(255), nullable=True)
    is_system: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )
    active_character_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("characters.id"), nullable=True
    )
    # The makerspace this person primarily belongs to (profile attribute).
    primary_space_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("spaces.id"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
