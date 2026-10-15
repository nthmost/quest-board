"""Space (makerspace) read helpers."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Space


def list_spaces(db: Session, include_inactive: bool = False) -> list[Space]:
    stmt = select(Space)
    if not include_inactive:
        stmt = stmt.where(Space.is_active.is_(True))
    stmt = stmt.order_by(Space.sort_order, Space.name)
    return list(db.execute(stmt).scalars().all())


def get_space(db: Session, space_id: int | None) -> Space | None:
    if space_id is None:
        return None
    return db.get(Space, space_id)


def space_name(db: Session, space_id: int | None) -> str | None:
    s = get_space(db, space_id)
    return s.name if s else None
