"""Read queries against quests. Filtering, cursor pagination, single-row fetch."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Quest
from app.services.cursor import decode_cursor

DEFAULT_PAGE_SIZE = 50
MAX_PAGE_SIZE = 200


def list_quests(
    db: Session,
    status: str | None = None,
    guild_id: int | None = None,
    location_id: int | None = None,
    parent_id: int | None = None,
    cursor: str | None = None,
    limit: int = DEFAULT_PAGE_SIZE,
    include_deleted: bool = False,
) -> list[Quest]:
    """List quests, newest first, with optional filters and cursor pagination."""
    stmt = _base_quest_query(include_deleted)
    stmt = _apply_filters(stmt, status, guild_id, location_id, parent_id)
    stmt = _apply_cursor(stmt, cursor)
    stmt = stmt.order_by(Quest.created_at.desc(), Quest.id.desc()).limit(_clamp_limit(limit))
    return list(db.execute(stmt).scalars().all())


def get_quest(db: Session, quest_id: int, include_deleted: bool = False) -> Quest | None:
    """Fetch a single quest by id. Returns None if not found or (when not allowed) deleted."""
    stmt = _base_quest_query(include_deleted).where(Quest.id == quest_id)
    return db.execute(stmt).scalar_one_or_none()


def _base_quest_query(include_deleted: bool):
    stmt = select(Quest)
    if not include_deleted:
        stmt = stmt.where(Quest.deleted_at.is_(None))
    return stmt


def _apply_filters(stmt, status, guild_id, location_id, parent_id):
    if status:
        stmt = stmt.where(Quest.status == status)
    if guild_id is not None:
        stmt = stmt.where(Quest.guild_id == guild_id)
    if location_id is not None:
        stmt = stmt.where(Quest.location_id == location_id)
    if parent_id is not None:
        stmt = stmt.where(Quest.parent_quest_id == parent_id)
    return stmt


def _apply_cursor(stmt, cursor: str | None):
    if not cursor:
        return stmt
    created_at, row_id = decode_cursor(cursor)
    return stmt.where(
        (Quest.created_at < created_at)
        | ((Quest.created_at == created_at) & (Quest.id < row_id))
    )


def _clamp_limit(limit: int) -> int:
    return max(1, min(limit, MAX_PAGE_SIZE))
