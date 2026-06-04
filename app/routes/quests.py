"""Quest read endpoints: GET /quests, GET /quests/{id}.

Auth/write paths are stubbed; this slice is read-only with public-safe field filtering.
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Quest
from app.schemas.quest import QuestList, QuestPublic
from app.services.cursor import encode_cursor
from app.services.quest_queries import DEFAULT_PAGE_SIZE, get_quest, list_quests
from app.services.quest_serializer import to_public

router = APIRouter(prefix="/quests", tags=["quests"])


@router.get("", response_model=QuestList)
def get_quests(
    db: Session = Depends(get_db),
    status: str | None = None,
    guild_id: int | None = None,
    location_id: int | None = None,
    parent_id: int | None = None,
    cursor: str | None = None,
    limit: int = Query(DEFAULT_PAGE_SIZE, ge=1, le=200),
) -> QuestList:
    rows = list_quests(db, status, guild_id, location_id, parent_id, cursor, limit)
    items = [to_public(db, q) for q in rows]
    return QuestList(items=items, next_cursor=_next_cursor(rows, limit))


@router.get("/{quest_id}", response_model=QuestPublic)
def get_quest_detail(quest_id: int, db: Session = Depends(get_db)) -> QuestPublic:
    quest = get_quest(db, quest_id)
    _reject_if_missing_or_deleted(quest, quest_id, db)
    return to_public(db, quest)


def _next_cursor(rows: list[Quest], limit: int) -> str | None:
    """Return cursor pointing past the last row only if we filled the page."""
    if len(rows) < limit:
        return None
    last = rows[-1]
    return encode_cursor(last.created_at, last.id)


def _reject_if_missing_or_deleted(quest: Quest | None, quest_id: int, db: Session) -> None:
    if quest is not None:
        return
    deleted = get_quest(db, quest_id, include_deleted=True)
    if deleted is not None and deleted.deleted_at is not None:
        raise HTTPException(status_code=410, detail="deleted")
    raise HTTPException(status_code=404, detail="not found")
