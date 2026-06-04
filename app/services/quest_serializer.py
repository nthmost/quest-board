"""Convert Quest ORM rows to QuestPublic / QuestFull, attaching aggregates."""

from sqlalchemy.orm import Session

from app.models import Quest
from app.schemas.quest import QuestFull, QuestPublic
from app.services.quest_aggregates import boost_summary, claim_count


def to_public(db: Session, quest: Quest) -> QuestPublic:
    """Public-safe view: omits creator id, fees, internal notes, claimer list."""
    return QuestPublic(
        **_base_fields(quest),
        claim_count=claim_count(db, quest.id),
        **boost_summary(db, quest),
    )


def to_full(db: Session, quest: Quest) -> QuestFull:
    """Authed view: includes everything public has plus sensitive fields."""
    return QuestFull(
        **_base_fields(quest),
        claim_count=claim_count(db, quest.id),
        **boost_summary(db, quest),
        **_sensitive_fields(quest),
    )


def _base_fields(quest: Quest) -> dict:
    """Fields shared between public and full views."""
    return {
        "id": quest.id,
        "parent_quest_id": quest.parent_quest_id,
        "depth": quest.depth,
        "rollup_mode": quest.rollup_mode,
        "creator_attribution": quest.creator_attribution,
        "guild_id": quest.guild_id,
        "location_id": quest.location_id,
        "title": quest.title,
        "description": quest.description,
        "skills": list(quest.skills),
        "xp": quest.xp,
        "xp_source": quest.xp_source,
        "urgency": quest.urgency,
        "due_date": quest.due_date,
        "party_min": quest.party_min,
        "party_max": quest.party_max,
        "status": quest.status,
        "paid_out_at": quest.paid_out_at,
        "done_at": quest.done_at,
        "verified_at": quest.verified_at,
        "created_at": quest.created_at,
    }


def _sensitive_fields(quest: Quest) -> dict:
    """Fields that only authed callers see."""
    return {
        "creator_user_id": quest.creator_user_id,
        "creator_bonus_xp": quest.creator_bonus_xp,
        "verifier_bonus_xp": quest.verifier_bonus_xp,
        "posting_fee_charged": quest.posting_fee_charged,
        "posting_fee_destination": quest.posting_fee_destination,
        "requires_verification": quest.requires_verification,
        "verifier_user_ids": list(quest.verifier_user_ids),
        "internal_notes": quest.internal_notes,
    }
