"""Quest creation eligibility: privileged list + threshold gate."""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.auth import is_admin
from app.config import load_economy
from app.models import Character, XpTransaction


@dataclass
class CreationEligibility:
    allowed: bool
    reason: str        # shown in tooltip when blocked
    privileged: bool   # bypassed via allowlist (not threshold)


def check(db: Session, username: str | None, character: Character | None) -> CreationEligibility:
    """Return eligibility for the given user+character to create a quest."""
    if not username:
        return CreationEligibility(False, "Log in to create quests.", False)

    cfg = load_economy().get("quest_creation", {})

    # Admins always pass
    if is_admin(username):
        return CreationEligibility(True, "", True)

    # Privileged allowlist
    privileged = {u.lower() for u in (cfg.get("privileged_usernames") or [])}
    if username.lower() in privileged:
        return CreationEligibility(True, "", True)

    # Threshold gate
    gate = cfg.get("gate") or {}
    min_done = gate.get("min_quests_completed") or 0
    min_level = gate.get("min_level") or 0

    if character is None:
        return CreationEligibility(
            False, "Create a character first, then complete some quests.", False,
        )

    if min_level and character.level >= min_level:
        return CreationEligibility(True, "", False)

    quests_done = _paid_quest_count(db, character.id)
    if min_done and quests_done >= min_done:
        return CreationEligibility(True, "", False)

    # Build a helpful message describing what's still needed
    parts = []
    if min_done:
        parts.append(f"complete {min_done} quest{'s' if min_done != 1 else ''} ({quests_done}/{min_done})")
    if min_level:
        parts.append(f"reach level {min_level} (currently {character.level})")
    reason = "To post quests: " + (" or ".join(parts)) + "."
    return CreationEligibility(False, reason, False)


def _paid_quest_count(db: Session, character_id: int) -> int:
    stmt = (
        select(func.count())
        .select_from(XpTransaction)
        .where(
            XpTransaction.character_id == character_id,
            XpTransaction.reason == "quest_completion",
        )
    )
    return int(db.execute(stmt).scalar_one() or 0)
