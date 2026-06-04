"""Quest model. Single core entity; sub-quests are quests with parent_quest_id set."""

from datetime import datetime

from sqlalchemy import (
    ARRAY,
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    String,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class Quest(Base):
    __tablename__ = "quests"
    __table_args__ = (
        CheckConstraint(
            "(paid_out_at IS NULL) OR (status IN ('done','verified'))",
            name="quests_paid_out_implies_terminal",
        ),
        CheckConstraint("depth >= 0 AND depth <= 3", name="quests_depth_in_range"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    parent_quest_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("quests.id"), nullable=True, index=True
    )
    depth: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    rollup_mode: Mapped[str] = mapped_column(
        String(16), nullable=False, default="manual", server_default="manual"
    )
    creator_user_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("users.id"), nullable=True
    )
    creator_character_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("characters.id"), nullable=True, index=True
    )
    creator_npc_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("npc_quest_givers.id"), nullable=True
    )
    creator_attribution: Mapped[str | None] = mapped_column(String(255), nullable=True)
    guild_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("guilds.id"), nullable=True, index=True
    )
    location_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("locations.id"), nullable=True, index=True
    )
    title: Mapped[str] = mapped_column(String(512), nullable=False)
    description: Mapped[str] = mapped_column(String, nullable=False)
    skills: Mapped[list[str]] = mapped_column(
        ARRAY(String), nullable=False, default=list, server_default="{}"
    )
    xp: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    xp_source: Mapped[str] = mapped_column(
        String(32), nullable=False, default="manual", server_default="manual"
    )
    creator_bonus_xp: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    verifier_bonus_xp: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    posting_fee_charged: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    posting_fee_destination: Mapped[str | None] = mapped_column(String(16), nullable=True)
    urgency: Mapped[str] = mapped_column(
        String(16), nullable=False, default="normal", server_default="normal"
    )
    due_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    party_min: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")
    party_max: Mapped[int | None] = mapped_column(Integer, nullable=True)
    requires_verification: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )
    verifier_user_ids: Mapped[list[int]] = mapped_column(
        ARRAY(BigInteger), nullable=False, default=list, server_default="{}"
    )
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, default="open", server_default="open", index=True
    )
    paid_out_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    done_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    internal_notes: Mapped[str | None] = mapped_column(String, nullable=True)
    contact_text: Mapped[str | None] = mapped_column(String, nullable=True)
    verifier_text: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )
