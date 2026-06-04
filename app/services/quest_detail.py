"""Shape a quest into a full render-ready dict for the detail page.

Public callers see a redacted view (no claim list, no creator identity);
authed callers see everything that's safe to expose to a logged-in user.
Mirror of SPEC.md §6 field visibility.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import (
    Character,
    Guild,
    Location,
    NpcQuestGiver,
    Quest,
    QuestBoost,
    QuestClaim,
    User,
)
from app.services.quest_aggregates import boost_summary


def get_detail(db: Session, quest_id: int, authed: bool) -> dict | None:
    """Return the rendered dict for `quest_id`, or None if missing/deleted."""
    quest = db.execute(select(Quest).where(Quest.id == quest_id)).scalar_one_or_none()
    if quest is None or quest.deleted_at is not None:
        return None
    return _shape_detail(db, quest, authed)


def _shape_detail(db: Session, quest: Quest, authed: bool) -> dict:
    return {
        **_base_fields(quest),
        "guild": _guild_block(db, quest.guild_id),
        "location": _location_block(db, quest.location_id),
        "creator": _creator_block(db, quest, authed),
        "claims": _claims_block(db, quest.id, authed),
        "boost_summary": boost_summary(db, quest),
        "boost_detail": _boost_detail_block(db, quest.id) if authed else None,
        "parent": _parent_block(db, quest.parent_quest_id),
        "children": _children_block(db, quest.id),
        **_authed_only_fields(quest, authed),
    }


def _base_fields(quest: Quest) -> dict:
    return {
        "id": quest.id,
        "title": quest.title,
        "description": quest.description,
        "status": quest.status,
        "urgency": quest.urgency,
        "xp": quest.xp,
        "skills": list(quest.skills or []),
        "party_min": quest.party_min,
        "party_max": quest.party_max,
        "due_date": quest.due_date,
        "rollup_mode": quest.rollup_mode,
        "depth": quest.depth,
        "contact_text": quest.contact_text,
        "verifier_text": quest.verifier_text,
        "created_at": quest.created_at,
        "done_at": quest.done_at,
        "verified_at": quest.verified_at,
        "paid_out_at": quest.paid_out_at,
    }


def _authed_only_fields(quest: Quest, authed: bool) -> dict:
    if not authed:
        return {
            "creator_bonus_xp": None,
            "verifier_bonus_xp": None,
            "posting_fee_charged": None,
            "posting_fee_destination": None,
            "internal_notes": None,
            "requires_verification": None,
            "verifier_user_ids": None,
            "creator_user_id": None,
        }
    return {
        "creator_bonus_xp": quest.creator_bonus_xp,
        "verifier_bonus_xp": quest.verifier_bonus_xp,
        "posting_fee_charged": quest.posting_fee_charged,
        "posting_fee_destination": quest.posting_fee_destination,
        "internal_notes": quest.internal_notes,
        "requires_verification": quest.requires_verification,
        "verifier_user_ids": list(quest.verifier_user_ids or []),
        "creator_user_id": quest.creator_user_id,
    }


def _guild_block(db: Session, guild_id: int | None) -> dict | None:
    if guild_id is None:
        return None
    g = db.execute(select(Guild).where(Guild.id == guild_id)).scalar_one_or_none()
    if g is None:
        return None
    return {"slug": g.slug, "name": g.name, "description": g.description}


def _location_block(db: Session, location_id: int | None) -> dict | None:
    if location_id is None:
        return None
    loc = db.execute(select(Location).where(Location.id == location_id)).scalar_one_or_none()
    if loc is None:
        return None
    return {
        "slug": loc.slug,
        "name": loc.name,
        "kind": loc.kind,
        "description": loc.description,
    }


SYSTEM_ATTRIBUTION = {"kind": "system", "name": "The Quartermaster"}


def _creator_block(db: Session, quest: Quest, _authed: bool) -> dict:
    """Resolve the quest's poster. Characters and NPCs are the primary actors;
    everything else (admin/service-principal user_id, plain user_id, or no FK
    at all) reads as the system voice — The Quartermaster.

    The creator_user_id field is still recorded in the DB for audit, but it
    isn't surfaced on the detail page. Admins can query it directly.
    """
    if quest.creator_npc_id is not None:
        return _npc_creator(db, quest.creator_npc_id) or SYSTEM_ATTRIBUTION
    if quest.creator_character_id is not None:
        return _character_creator(db, quest.creator_character_id, _authed) or SYSTEM_ATTRIBUTION
    if quest.creator_attribution:
        return {"kind": "attribution", "name": quest.creator_attribution}
    return SYSTEM_ATTRIBUTION


def _npc_creator(db: Session, npc_id: int) -> dict | None:
    npc = db.execute(
        select(NpcQuestGiver).where(NpcQuestGiver.id == npc_id)
    ).scalar_one_or_none()
    if npc is None:
        return None
    return {"kind": "npc", "name": npc.display_name, "handle": npc.handle}


def _character_creator(db: Session, char_id: int, authed: bool) -> dict | None:
    char = db.execute(select(Character).where(Character.id == char_id)).scalar_one_or_none()
    if char is None:
        return None
    out = {"kind": "character", "name": char.name, "id": char.id, "class": char.class_slug}
    if authed:
        owner = db.execute(select(User).where(User.id == char.user_id)).scalar_one_or_none()
        out["wiki_username"] = owner.wiki_username if owner else None
    return out


def _user_creator(db: Session, user_id: int, authed: bool) -> dict | None:
    """Reserved for future admin-detail surfaces. Not used by _creator_block —
    user-id-only quests are treated as system posts on the public detail page.
    """
    if not authed:
        return {"kind": "user", "name": "(member)"}
    u = db.execute(select(User).where(User.id == user_id)).scalar_one_or_none()
    if u is None:
        return None
    return {"kind": "user", "name": u.wiki_username, "wiki_username": u.wiki_username}


def _claims_block(db: Session, quest_id: int, authed: bool) -> dict:
    """Public: just an active count. Authed: full list with character names."""
    rows = db.execute(
        select(QuestClaim, Character.name)
        .join(Character, Character.id == QuestClaim.character_id)
        .where(QuestClaim.quest_id == quest_id)
        .order_by(QuestClaim.claimed_at.asc())
    ).all()
    active = [r for r in rows if r[0].released_at is None]
    summary = {"active_count": len(active), "total_count": len(rows)}
    if not authed:
        return summary
    summary["active"] = [
        {"character_name": name, "claimed_at": claim.claimed_at}
        for claim, name in active
    ]
    summary["released"] = [
        {"character_name": name, "claimed_at": claim.claimed_at,
         "released_at": claim.released_at}
        for claim, name in rows if claim.released_at is not None
    ]
    return summary


def _boost_detail_block(db: Session, quest_id: int) -> list[dict]:
    rows = db.execute(
        select(QuestBoost, Character.name)
        .join(Character, Character.id == QuestBoost.booster_character_id)
        .where(QuestBoost.quest_id == quest_id)
        .order_by(QuestBoost.created_at.asc())
    ).all()
    return [
        {
            "booster_name": name,
            "amount": boost.amount,
            "is_self_boost": boost.is_self_boost,
            "refunded": boost.refunded_at is not None,
            "created_at": boost.created_at,
        }
        for boost, name in rows
    ]


def _parent_block(db: Session, parent_id: int | None) -> dict | None:
    if parent_id is None:
        return None
    p = db.execute(select(Quest).where(Quest.id == parent_id)).scalar_one_or_none()
    if p is None or p.deleted_at is not None:
        return None
    return {"id": p.id, "title": p.title, "status": p.status}


def _children_block(db: Session, quest_id: int) -> list[dict]:
    rows = db.execute(
        select(Quest)
        .where(Quest.parent_quest_id == quest_id, Quest.deleted_at.is_(None))
        .order_by(Quest.created_at.asc())
    ).scalars().all()
    return [
        {"id": q.id, "title": q.title, "status": q.status, "xp": q.xp}
        for q in rows
    ]
