from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Guild, Location, Quest
from app.models.character import Character


def recommend(db: Session, character: Character, limit: int = 8) -> list[dict]:
    now = datetime.now(timezone.utc)

    stmt = (
        select(Quest, Guild.slug.label("g_slug"), Location.slug.label("l_slug"))
        .outerjoin(Guild, Guild.id == Quest.guild_id)
        .outerjoin(Location, Location.id == Quest.location_id)
        .where(Quest.status == "open", Quest.deleted_at.is_(None))
    )
    rows = db.execute(stmt).all()

    scored: list[tuple[int, Quest, str | None, str | None]] = []
    for quest, g_slug, l_slug in rows:
        score = 0
        if character.primary_guild_id is not None and quest.guild_id == character.primary_guild_id:
            score += 10
        if quest.urgency == "high":
            score += 3
        created = quest.created_at
        if created.tzinfo is None:
            created = created.replace(tzinfo=timezone.utc)
        age_days = (now - created).days
        if age_days <= 7:
            score += 2
        elif age_days <= 30:
            score += 1
        scored.append((score, quest, g_slug, l_slug))

    scored.sort(key=lambda t: (t[0], t[1].created_at), reverse=True)

    return [
        {
            "id": quest.id,
            "title": quest.title,
            "xp": quest.xp,
            "urgency": quest.urgency,
            "guild_slug": g_slug,
            "location_slug": l_slug,
            "party_min": quest.party_min,
            "party_max": quest.party_max,
            "skills": quest.skills,
            "score": score,
        }
        for score, quest, g_slug, l_slug in scored[:limit]
    ]
