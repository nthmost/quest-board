"""Meta endpoints: /healthz, /version, /stats, /economy."""

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app import __version__
from app.config import get_public_economy, load_economy
from app.db import get_db
from app.models import Quest, User, XpTransaction
from app.schemas.meta import EconomyOut, HealthOut, StatsOut, VersionOut

router = APIRouter(tags=["meta"])


@router.get("/healthz", response_model=HealthOut)
def healthz() -> HealthOut:
    return HealthOut()


@router.get("/version", response_model=VersionOut)
def version() -> VersionOut:
    return VersionOut(version=__version__)


@router.get("/economy", response_model=EconomyOut)
def economy() -> EconomyOut:
    return EconomyOut(config=get_public_economy())


@router.get("/stats", response_model=StatsOut)
def stats(db: Session = Depends(get_db)) -> StatsOut:
    return StatsOut(
        quest_count=_count_quests(db, deleted=False),
        quests_open=_count_quests_with_status(db, "open"),
        quests_done=_count_quests_with_status(db, "done"),
        user_count=_count_users(db),
        total_xp_minted=_sum_minted(db),
        total_xp_burned=_sum_burned(db),
        gold_standard_set_size=_gold_standard_size(db),
        calibration_status=_calibration_status(db),
        economy_warnings=_economy_warnings(),
    )


def _count_quests(db: Session, deleted: bool) -> int:
    stmt = select(func.count()).select_from(Quest)
    if not deleted:
        stmt = stmt.where(Quest.deleted_at.is_(None))
    return db.execute(stmt).scalar_one()


def _count_quests_with_status(db: Session, status: str) -> int:
    stmt = (
        select(func.count())
        .select_from(Quest)
        .where(Quest.deleted_at.is_(None), Quest.status == status)
    )
    return db.execute(stmt).scalar_one()


def _count_users(db: Session) -> int:
    stmt = select(func.count()).select_from(User).where(User.is_system.is_(False))
    return db.execute(stmt).scalar_one()


def _sum_minted(db: Session) -> int:
    stmt = select(func.coalesce(func.sum(XpTransaction.amount), 0)).where(
        XpTransaction.amount > 0
    )
    return db.execute(stmt).scalar_one()


def _sum_burned(db: Session) -> int:
    stmt = select(func.coalesce(func.sum(XpTransaction.amount), 0)).where(
        XpTransaction.amount < 0
    )
    return -db.execute(stmt).scalar_one()


def _gold_standard_size(db: Session) -> int:
    stmt = (
        select(func.count())
        .select_from(Quest)
        .where(Quest.xp_source == "manual", Quest.xp > 0, Quest.deleted_at.is_(None))
    )
    return db.execute(stmt).scalar_one()


def _calibration_status(db: Session) -> str:
    xp_cfg = load_economy().get("xp", {})
    threshold = xp_cfg.get("llm_xp_suggestion", {}).get("threshold_quests", 20)
    return "calibrated" if _gold_standard_size(db) >= threshold else "bootstrap"


def _economy_warnings() -> list[str]:
    """Surface config consistency warnings (e.g. posting_fee on but welcome_grant off)."""
    warnings: list[str] = []
    cfg = load_economy().get("xp", {})
    fee = cfg.get("posting_fee", {})
    grant = cfg.get("welcome_grant", {})
    if fee.get("enabled") and not grant.get("enabled"):
        warnings.append("posting_fee enabled but welcome_grant disabled — new users cannot post")
    if (
        fee.get("enabled")
        and grant.get("enabled")
        and grant.get("amount", 0) < fee.get("flat_amount", 0)
    ):
        warnings.append("welcome_grant.amount is smaller than posting_fee.flat_amount")
    return warnings
