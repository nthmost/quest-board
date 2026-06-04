"""Per-quest aggregate computations: claim counts, boost pools."""

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Quest, QuestBoost, QuestClaim


def claim_count(db: Session, quest_id: int) -> int:
    """Number of currently-active claims (released_at IS NULL)."""
    stmt = select(func.count()).select_from(QuestClaim).where(
        QuestClaim.quest_id == quest_id, QuestClaim.released_at.is_(None)
    )
    return db.execute(stmt).scalar_one()


def boost_summary(db: Session, quest: Quest) -> dict[str, int]:
    """Return total/external/self boost amounts and count for a quest."""
    rows = db.execute(_boost_query(quest.id)).all()
    return _summarize_boosts(rows, quest.creator_character_id)


def _boost_query(quest_id: int):
    return (
        select(QuestBoost.amount, QuestBoost.is_self_boost, QuestBoost.booster_character_id)
        .where(QuestBoost.quest_id == quest_id)
        .where(QuestBoost.refunded_at.is_(None))
    )


def _summarize_boosts(rows: list, creator_character_id: int | None) -> dict[str, int]:
    total = sum(r.amount for r in rows)
    self_amount = sum(
        r.amount for r in rows if r.booster_character_id == creator_character_id
    )
    return {
        "total_boost_pool": total,
        "external_boost_pool": total - self_amount,
        "self_boost_amount": self_amount,
        "boost_count": len(rows),
    }
