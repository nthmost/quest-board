"""XpTransaction: the ledger. Every balance change is a row here."""

from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class XpTransaction(Base):
    __tablename__ = "xp_transactions"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    character_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("characters.id"), nullable=False, index=True
    )
    amount: Mapped[int] = mapped_column(Integer, nullable=False)
    reason: Mapped[str] = mapped_column(String(48), nullable=False)
    quest_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("quests.id"), nullable=True, index=True
    )
    boost_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("quest_boosts.id"), nullable=True
    )
    memo: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    created_by_user_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("users.id"), nullable=True
    )
