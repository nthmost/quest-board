"""NpcQuestGiver: simulator-driven posters. Not users, not characters."""

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class NpcQuestGiver(Base):
    __tablename__ = "npc_quest_givers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    handle: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    display_name: Mapped[str] = mapped_column(String(128), nullable=False)
    guild_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("guilds.id"), nullable=True
    )
    post_cadence_sec: Mapped[int] = mapped_column(Integer, nullable=False)
    description: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
