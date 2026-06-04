"""QuestBoost: tracks per-user XP contributions to a quest's payout pool."""

from datetime import datetime

from sqlalchemy import BigInteger, Boolean, CheckConstraint, DateTime, ForeignKey, Integer, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class QuestBoost(Base):
    __tablename__ = "quest_boosts"
    __table_args__ = (CheckConstraint("amount > 0", name="quest_boosts_amount_positive"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    quest_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("quests.id"), nullable=False, index=True
    )
    booster_character_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("characters.id"), nullable=False
    )
    amount: Mapped[int] = mapped_column(Integer, nullable=False)
    is_self_boost: Mapped[bool] = mapped_column(Boolean, nullable=False)
    spend_txn_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("xp_transactions.id"), nullable=False
    )
    refund_txn_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("xp_transactions.id"), nullable=True
    )
    refunded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
