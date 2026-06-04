"""Claim / release / complete / verify a quest.

State machine (per SPEC.md §7):
  open + active_count >= party_min  → claimed
  claimed + active_count <  party_min → open
  claimed/open + complete()          → done (+ immediate XP if no verification)
  done + verify()                    → verified + XP payout
"""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Character, Quest, QuestClaim, XpTransaction
from app.services.levels import level_for_xp


class QuestActionError(ValueError):
    """User-facing failure reason during claim/release/complete/verify."""


def claim(db: Session, character: Character, quest_id: int) -> Quest:
    """Insert a claim for the given character on the given quest.

    Validates: quest exists / not deleted / not paid out / not done|verified;
    party_max not exceeded; this character isn't already actively claiming.
    Promotes quest to 'claimed' if claim count meets party_min.
    """
    quest = _live_quest_or_die(db, quest_id)
    _reject_if_terminal(quest)
    _reject_if_full(db, quest)
    _reject_if_already_claiming(db, quest_id, character.id)

    db.add(QuestClaim(quest_id=quest_id, character_id=character.id))
    db.flush()
    _maybe_advance_status(db, quest)
    db.commit()
    db.refresh(quest)
    return quest


def release(db: Session, character: Character, quest_id: int) -> Quest:
    """Mark this character's active claim as released. Demotes status if needed."""
    quest = _live_quest_or_die(db, quest_id)
    active = _active_claim(db, quest_id, character.id)
    if active is None:
        raise QuestActionError("You don't have an active claim on this quest.")
    active.released_at = datetime.now(UTC)
    db.flush()
    _maybe_advance_status(db, quest)
    db.commit()
    db.refresh(quest)
    return quest


def complete(
    db: Session,
    character: Character,
    quest_id: int,
    done_state: str = "full",
    claim_notes: str | None = None,
    time_spent_minutes: int | None = None,
) -> Quest:
    """Mark the character's active claim done.

    If quest.requires_verification is False, XP pays out immediately.
    If True, quest moves to 'done' with XP held until verify() is called.
    """
    quest = _live_quest_or_die(db, quest_id)
    _reject_if_terminal(quest)
    active = _active_claim(db, quest_id, character.id)
    if active is None:
        raise QuestActionError("You don't have an active claim on this quest.")
    now = datetime.now(UTC)
    active.done_state = done_state
    active.claim_notes = claim_notes
    active.time_spent_minutes = time_spent_minutes
    active.reported_at = now
    quest.status = "done"
    quest.done_at = now
    db.flush()
    if not quest.requires_verification:
        _payout(db, quest, now)
    db.commit()
    db.refresh(quest)
    return quest


def verify(
    db: Session,
    user_id: int,
    quest_id: int,
    is_admin: bool = False,
) -> Quest:
    """Approve a done quest, releasing held XP to claimers.

    Authorization: admin always allowed; otherwise caller must be in
    verifier_user_ids, or the quest creator when verifier_user_ids is empty.
    """
    quest = _live_quest_or_die(db, quest_id)
    if quest.status != "done":
        raise QuestActionError("Quest must be in 'done' state to verify.")
    if quest.paid_out_at is not None:
        raise QuestActionError("Quest is already paid out.")
    if not is_admin and not _is_authorized_verifier(quest, user_id):
        raise QuestActionError("You are not authorized to verify this quest.")
    now = datetime.now(UTC)
    quest.status = "verified"
    quest.verified_at = now
    _payout(db, quest, now)
    db.commit()
    db.refresh(quest)
    return quest


def has_active_claim(db: Session, character_id: int, quest_id: int) -> bool:
    return _active_claim(db, quest_id, character_id) is not None


def active_claim_count(db: Session, quest_id: int) -> int:
    stmt = (
        select(func.count())
        .select_from(QuestClaim)
        .where(QuestClaim.quest_id == quest_id, QuestClaim.released_at.is_(None))
    )
    return int(db.execute(stmt).scalar_one() or 0)


def _live_quest_or_die(db: Session, quest_id: int) -> Quest:
    quest = db.execute(select(Quest).where(Quest.id == quest_id)).scalar_one_or_none()
    if quest is None or quest.deleted_at is not None:
        raise QuestActionError("Quest not found.")
    return quest


def _reject_if_terminal(quest: Quest) -> None:
    if quest.paid_out_at is not None:
        raise QuestActionError("This quest is already paid out.")
    if quest.status not in ("open", "claimed"):
        raise QuestActionError(f"Quest is {quest.status}; can't claim.")


def _reject_if_full(db: Session, quest: Quest) -> None:
    if quest.party_max is None:
        return
    if active_claim_count(db, quest.id) >= quest.party_max:
        raise QuestActionError("This quest's party is already full.")


def _reject_if_already_claiming(db: Session, quest_id: int, character_id: int) -> None:
    if _active_claim(db, quest_id, character_id) is not None:
        raise QuestActionError("You're already on this quest.")


def _is_authorized_verifier(quest: Quest, user_id: int) -> bool:
    if quest.verifier_user_ids and user_id in quest.verifier_user_ids:
        return True
    # Empty list = creator only
    if not quest.verifier_user_ids and quest.creator_user_id == user_id:
        return True
    return False


def _active_claim(db: Session, quest_id: int, character_id: int) -> QuestClaim | None:
    stmt = (
        select(QuestClaim)
        .where(
            QuestClaim.quest_id == quest_id,
            QuestClaim.character_id == character_id,
            QuestClaim.released_at.is_(None),
        )
        .limit(1)
    )
    return db.execute(stmt).scalar_one_or_none()


def _maybe_advance_status(db: Session, quest: Quest) -> None:
    """Move open → claimed when count reaches party_min, or back when below."""
    count = active_claim_count(db, quest.id)
    if quest.status == "open" and count >= quest.party_min:
        quest.status = "claimed"
    elif quest.status == "claimed" and count < quest.party_min:
        quest.status = "open"


def _payout(db: Session, quest: Quest, now: datetime) -> None:
    """Mint XP for all active claimers and set paid_out_at. Caller sets status."""
    quest.paid_out_at = now
    active_claims = db.execute(
        select(QuestClaim).where(
            QuestClaim.quest_id == quest.id,
            QuestClaim.released_at.is_(None),
        )
    ).scalars().all()
    for claim in active_claims:
        char = db.execute(
            select(Character).where(Character.id == claim.character_id)
        ).scalar_one()
        _mint_xp(db, char, quest.xp, "quest_completion", quest.id)
    if quest.creator_character_id is not None and quest.creator_bonus_xp > 0:
        creator = db.execute(
            select(Character).where(Character.id == quest.creator_character_id)
        ).scalar_one_or_none()
        if creator is not None:
            _mint_xp(db, creator, quest.creator_bonus_xp, "quest_creation_bonus", quest.id)


def charge_posting_fee(db: Session, char: Character, quest: Quest, fee: int) -> None:
    """Deduct posting fee from spendable balance and record it on the quest."""
    if fee <= 0:
        return
    char.xp_balance = max(0, char.xp_balance - fee)
    quest.posting_fee_charged = fee
    quest.posting_fee_destination = "burn"
    db.add(XpTransaction(
        character_id=char.id,
        amount=-fee,
        reason="posting_fee",
        quest_id=quest.id,
    ))


def _mint_xp(db: Session, char: Character, amount: int, reason: str, quest_id: int) -> None:
    if amount <= 0:
        return
    char.xp_balance += amount
    char.total_xp_earned += amount
    db.add(XpTransaction(
        character_id=char.id,
        amount=amount,
        reason=reason,
        quest_id=quest_id,
    ))
    new_level = level_for_xp(char.total_xp_earned)
    if new_level > char.level:
        char.level = new_level
