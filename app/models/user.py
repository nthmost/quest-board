"""User model: pure identity. Economy lives on Character."""

from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    # `wiki_username` is the stored identity column (name kept for schema
    # stability); it now holds the person's public **handle** — the name they
    # log in with and the only name others see unless they opt in below.
    wiki_username: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    # Real name: collected at signup (required there) but unenforced/unverified
    # and private by default. Nullable in the DB for legacy/system rows.
    real_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    # When true, this person's real name is shown alongside their handle to
    # everyone, as "handle (Real Name)". Off by default — pseudonymous.
    show_real_name: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )
    # Argon2id hash for independent login. Null for legacy/system rows with
    # no password set.
    password_hash: Mapped[str | None] = mapped_column(String(255), nullable=True)
    wiki_user_id: Mapped[int | None] = mapped_column(BigInteger, unique=True, nullable=True)
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
