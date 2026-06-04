"""QuestClaim: a character's active or historical claim on a quest."""

from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class QuestClaim(Base):
    __tablename__ = "quest_claims"

    quest_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("quests.id"), primary_key=True
    )
    character_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("characters.id"), primary_key=True
    )
    claimed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), primary_key=True, server_default=func.now()
    )
    released_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    done_state: Mapped[str | None] = mapped_column(String(16), nullable=True)
    claim_notes: Mapped[str | None] = mapped_column(String, nullable=True)
    time_spent_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    reported_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
