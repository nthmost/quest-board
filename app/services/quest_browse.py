"""Filterable, sortable, paginated quest list for the public /quests page.

Public-safe shaping: omits creator identity, internal notes, and fee
details (those are visible only on the per-quest detail page when authed,
or in /admin/*). Returns just enough to render a card.
"""

from __future__ import annotations

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.models import Guild, Location, Quest, QuestClaim

VALID_STATUSES = {"open", "claimed", "done", "verified"}
VALID_URGENCIES = {"low", "normal", "high"}
VALID_SORTS = {"newest", "oldest", "xp_high", "xp_low", "urgent"}
DEFAULT_PAGE_SIZE = 30


def browse(
    db: Session,
    *,
    q: str = "",
    status: str | None = None,
    guild_slug: str | None = None,
    location_slug: str | None = None,
    skill: str = "",
    xp_min: int | None = None,
    xp_max: int | None = None,
    urgency: str | None = None,
    sort: str = "newest",
    page: int = 1,
    page_size: int = DEFAULT_PAGE_SIZE,
) -> dict:
    """Return a page of quests + metadata. All filter values are optional."""
    page = max(1, page)
    page_size = max(1, min(page_size, 100))
    base = _filtered_query(db, q, status, guild_slug, location_slug, skill, xp_min, xp_max, urgency)
    total = _count(db, base)
    rows = _paginate(db, _ordered(base, sort), page, page_size)
    return {
        "quests": [_shape_row(db, row) for row in rows],
        "page": page,
        "page_size": page_size,
        "total": total,
        "page_count": max(1, (total + page_size - 1) // page_size),
        "filters": {
            "q": q,
            "status": status or "",
            "guild_slug": guild_slug or "",
            "location_slug": location_slug or "",
            "skill": skill,
            "xp_min": xp_min,
            "xp_max": xp_max,
            "urgency": urgency or "",
            "sort": sort,
        },
    }


def _filtered_query(
    db: Session, q: str, status: str | None,
    guild_slug: str | None, location_slug: str | None,
    skill: str = "", xp_min: int | None = None, xp_max: int | None = None,
    urgency: str | None = None,
):
    stmt = (
        select(Quest, Guild.slug.label("g_slug"), Location.slug.label("l_slug"))
        .outerjoin(Guild, Guild.id == Quest.guild_id)
        .outerjoin(Location, Location.id == Quest.location_id)
        .where(Quest.deleted_at.is_(None))
    )
    if q:
        like = f"%{q}%"
        stmt = stmt.where(or_(Quest.title.ilike(like), Quest.description.ilike(like)))
    if status in VALID_STATUSES:
        stmt = stmt.where(Quest.status == status)
    if guild_slug:
        stmt = stmt.where(Guild.slug == guild_slug)
    if location_slug:
        stmt = stmt.where(Location.slug == location_slug)
    if skill:
        stmt = stmt.where(func.array_position(Quest.skills, skill).isnot(None))
    if xp_min is not None:
        stmt = stmt.where(Quest.xp >= xp_min)
    if xp_max is not None:
        stmt = stmt.where(Quest.xp <= xp_max)
    if urgency in VALID_URGENCIES:
        stmt = stmt.where(Quest.urgency == urgency)
    return stmt


def _count(db: Session, stmt) -> int:
    counter = select(func.count()).select_from(stmt.subquery())
    return int(db.execute(counter).scalar_one() or 0)


def _ordered(stmt, sort: str):
    if sort == "oldest":
        return stmt.order_by(Quest.created_at.asc(), Quest.id.asc())
    if sort == "xp_high":
        return stmt.order_by(Quest.xp.desc(), Quest.created_at.desc())
    if sort == "xp_low":
        return stmt.order_by(Quest.xp.asc(), Quest.created_at.desc())
    if sort == "urgent":
        return stmt.order_by(
            (Quest.urgency == "high").desc(), Quest.created_at.desc(),
        )
    return stmt.order_by(Quest.created_at.desc(), Quest.id.desc())


def _paginate(db: Session, stmt, page: int, page_size: int) -> list:
    offset = (page - 1) * page_size
    return list(db.execute(stmt.offset(offset).limit(page_size)).all())


def _shape_row(db: Session, row) -> dict:
    quest, guild_slug, location_slug = row
    return {
        "id": quest.id,
        "title": quest.title,
        "xp": quest.xp,
        "status": quest.status,
        "urgency": quest.urgency,
        "guild_slug": guild_slug,
        "location_slug": location_slug,
        "party_min": quest.party_min,
        "party_max": quest.party_max,
        "created_at": quest.created_at,
        "claim_count": _claim_count(db, quest.id),
        "skills": quest.skills,
    }


def _claim_count(db: Session, quest_id: int) -> int:
    stmt = (
        select(func.count())
        .select_from(QuestClaim)
        .where(
            QuestClaim.quest_id == quest_id,
            QuestClaim.released_at.is_(None),
        )
    )
    return int(db.execute(stmt).scalar_one() or 0)


def list_filter_options(db: Session) -> dict:
    """Convenience: fetch all known guild + location slugs/names for dropdowns."""
    guilds = list(db.execute(select(Guild).order_by(Guild.name)).scalars().all())
    locations = list(db.execute(select(Location).order_by(Location.name)).scalars().all())
    return {"guilds": guilds, "locations": locations}


def distinct_skills(db: Session) -> list[str]:
    skill_col = func.unnest(Quest.skills).column_valued("skill")
    stmt = (
        select(skill_col)
        .select_from(Quest)
        .where(Quest.status == "open", Quest.deleted_at.is_(None))
        .distinct()
        .order_by(skill_col)
    )
    return [row[0] for row in db.execute(stmt).all()]
