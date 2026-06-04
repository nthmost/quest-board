"""Pydantic schemas for quests. Public vs full views are separate classes."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class QuestPublic(BaseModel):
    """Public-safe view: omits creator identity, claim list, internal notes, fee details."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    parent_quest_id: int | None
    depth: int
    rollup_mode: str
    creator_attribution: str | None
    guild_id: int | None
    location_id: int | None
    title: str
    description: str
    skills: list[str]
    xp: int
    xp_source: str
    urgency: str
    due_date: datetime | None
    party_min: int
    party_max: int | None
    status: str
    paid_out_at: datetime | None
    done_at: datetime | None
    verified_at: datetime | None
    created_at: datetime
    claim_count: int = 0
    total_boost_pool: int = 0
    external_boost_pool: int = 0
    self_boost_amount: int = 0
    boost_count: int = 0


class QuestFull(QuestPublic):
    """Authed view: adds creator identity, fee details, internal notes, verifier list."""

    creator_user_id: int | None
    creator_bonus_xp: int
    verifier_bonus_xp: int
    posting_fee_charged: int
    posting_fee_destination: str | None
    requires_verification: bool
    verifier_user_ids: list[int]
    internal_notes: str | None


class QuestList(BaseModel):
    items: list[QuestPublic]
    next_cursor: str | None
