"""Character: the primary actor in both modes. Owns XP and level."""

from datetime import datetime

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class Character(Base):
    __tablename__ = "characters"
    __table_args__ = (
        CheckConstraint("xp_balance >= 0", name="characters_xp_balance_nonneg"),
        UniqueConstraint("user_id", "name", name="characters_unique_name_per_user"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(64), nullable=False)
    class_slug: Mapped[str] = mapped_column(
        String(32), ForeignKey("character_classes.slug"), nullable=False
    )
    primary_guild_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("guilds.id"), nullable=True
    )
    xp_balance: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    total_xp_earned: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    level: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")
    flavor_seed: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
