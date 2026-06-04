"""Admin pages: dashboard, quests, users, templates.

Gated by `auth.require_admin` (wiki username must appear in
economy.yaml's admin.usernames). All read-only for now; sim controls
land when the simulator does.
"""

from collections import Counter
from functools import lru_cache
from pathlib import Path

import yaml
from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import desc, func, select
from sqlalchemy.orm import Session

from app.auth import require_admin
from app.db import get_db
from app.models import Quest, User

TEMPLATE_DIR = Path(__file__).resolve().parent.parent / "templates"
TEMPLATES = Jinja2Templates(directory=str(TEMPLATE_DIR))

POOL_PATH = Path("data/quest_templates/discord_tagged.yaml")

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("", response_class=HTMLResponse)
@router.get("/", response_class=HTMLResponse)
def dashboard(
    request: Request,
    username: str = Depends(require_admin),
    db: Session = Depends(get_db),
) -> HTMLResponse:
    return TEMPLATES.TemplateResponse(
        request, "admin_dashboard.html", _dashboard_context(username, db),
    )


@router.get("/quests", response_class=HTMLResponse)
def quests_page(
    request: Request,
    username: str = Depends(require_admin),
    db: Session = Depends(get_db),
    status: str | None = None,
    guild_slug: str | None = None,
    show_deleted: bool = False,
) -> HTMLResponse:
    rows = _list_quests(db, status, guild_slug, show_deleted)
    ctx = {
        "current_user": username,
        "rows": rows,
        "filters": {"status": status, "guild_slug": guild_slug, "show_deleted": show_deleted},
    }
    return TEMPLATES.TemplateResponse(request, "admin_quests.html", ctx)


@router.get("/users", response_class=HTMLResponse)
def users_page(
    request: Request,
    username: str = Depends(require_admin),
    db: Session = Depends(get_db),
) -> HTMLResponse:
    stmt = (
        select(User)
        .where(User.is_system.is_(False))
        .order_by(desc(User.last_seen_at).nulls_last(), User.created_at.desc())
    )
    rows = list(db.execute(stmt).scalars().all())
    return TEMPLATES.TemplateResponse(
        request, "admin_users.html",
        {"current_user": username, "rows": rows},
    )


@router.get("/quests/{quest_id}/edit", response_class=HTMLResponse)
def edit_quest_form(
    request: Request,
    quest_id: int,
    username: str = Depends(require_admin),
    db: Session = Depends(get_db),
) -> HTMLResponse:
    quest = _quest_or_die(db, quest_id)
    verifier_names = _ids_to_usernames(db, list(quest.verifier_user_ids or []))
    return TEMPLATES.TemplateResponse(
        request, "admin_quest_edit.html",
        {
            "current_user": username,
            "quest": quest,
            "verifier_usernames": ", ".join(verifier_names),
        },
    )


@router.post("/quests/{quest_id}/edit")
def edit_quest_submit(
    quest_id: int,
    username: str = Depends(require_admin),  # noqa: ARG001 — gate only
    db: Session = Depends(get_db),
    contact_text: str = Form(""),
    verifier_text: str = Form(""),
    internal_notes: str = Form(""),
    requires_verification: str = Form(""),
    verifier_usernames: str = Form(""),
) -> RedirectResponse:
    quest = _quest_or_die(db, quest_id)
    quest.contact_text = contact_text.strip() or None
    quest.verifier_text = verifier_text.strip() or None
    quest.internal_notes = internal_notes.strip() or None
    quest.requires_verification = requires_verification.lower() in ("true", "on", "1", "yes")
    quest.verifier_user_ids = _resolve_usernames(db, verifier_usernames)
    db.commit()
    return RedirectResponse(f"/quests/{quest_id}", status_code=303)


def _resolve_usernames(db: Session, raw: str) -> list[int]:
    """Convert comma-separated wiki usernames to user IDs, silently skipping unknowns."""
    names = [n.strip() for n in raw.split(",") if n.strip()]
    if not names:
        return []
    rows = db.execute(
        select(User.id).where(User.wiki_username.in_(names))
    ).all()
    return [r.id for r in rows]


def _ids_to_usernames(db: Session, ids: list[int]) -> list[str]:
    if not ids:
        return []
    rows = db.execute(
        select(User.wiki_username).where(User.id.in_(ids))
    ).all()
    return [r.wiki_username for r in rows]


def _quest_or_die(db: Session, quest_id: int) -> Quest:
    quest = db.execute(
        select(Quest).where(Quest.id == quest_id)
    ).scalar_one_or_none()
    if quest is None:
        raise HTTPException(status_code=404, detail="quest not found")
    return quest


@router.get("/templates", response_class=HTMLResponse)
def templates_page(
    request: Request,
    username: str = Depends(require_admin),
    channel: str | None = None,
    skill: str | None = None,
) -> HTMLResponse:
    pool = _load_pool()
    rows = _filter_pool(pool, channel, skill)
    ctx = {
        "current_user": username,
        "rows": rows,
        "channels": sorted({d["channel"] for d in pool}),
        "skills": _all_skills(pool),
        "filters": {"channel": channel, "skill": skill},
        "total": len(pool),
    }
    return TEMPLATES.TemplateResponse(request, "admin_templates.html", ctx)


def _dashboard_context(username: str, db: Session) -> dict:
    user_q = select(func.count()).select_from(User).where(User.is_system.is_(False))
    return {
        "current_user": username,
        "user_count": _scalar(db, user_q),
        "quest_stats": _quest_stats(db),
        "recent_users": _recent_users(db),
        "recent_quests": _recent_quests(db),
        "pool_stats": _pool_stats(),
    }


def _quest_stats(db: Session) -> dict:
    rows = db.execute(
        select(Quest.status, func.count())
        .where(Quest.deleted_at.is_(None))
        .group_by(Quest.status)
    ).all()
    by_status = {s: int(n) for s, n in rows}
    deleted_q = select(func.count()).select_from(Quest).where(Quest.deleted_at.is_not(None))
    return {**by_status, "deleted": _scalar(db, deleted_q)}


def _recent_users(db: Session, limit: int = 8) -> list[User]:
    stmt = (
        select(User)
        .where(User.is_system.is_(False))
        .order_by(User.created_at.desc())
        .limit(limit)
    )
    return list(db.execute(stmt).scalars().all())


def _recent_quests(db: Session, limit: int = 10) -> list[Quest]:
    stmt = select(Quest).order_by(Quest.created_at.desc()).limit(limit)
    return list(db.execute(stmt).scalars().all())


def _list_quests(
    db: Session, status: str | None, guild_slug: str | None, show_deleted: bool,
) -> list[Quest]:
    stmt = select(Quest)
    if not show_deleted:
        stmt = stmt.where(Quest.deleted_at.is_(None))
    if status:
        stmt = stmt.where(Quest.status == status)
    if guild_slug:
        # Resolved via join in the template; cheaper to filter here too if we had the id.
        pass
    stmt = stmt.order_by(Quest.created_at.desc()).limit(500)
    return list(db.execute(stmt).scalars().all())


@lru_cache(maxsize=1)
def _load_pool() -> list[dict]:
    if not POOL_PATH.exists():
        return []
    return yaml.safe_load(POOL_PATH.read_text()) or []


def _filter_pool(pool: list[dict], channel: str | None, skill: str | None) -> list[dict]:
    out = pool
    if channel:
        out = [d for d in out if d.get("channel") == channel]
    if skill:
        out = [d for d in out if skill in (d.get("skills") or [])]
    return out


def _all_skills(pool: list[dict]) -> list[str]:
    counter: Counter[str] = Counter()
    for d in pool:
        counter.update(d.get("skills") or [])
    return [s for s, _ in counter.most_common()]


def _pool_stats() -> dict:
    pool = _load_pool()
    by_channel = Counter(d["channel"] for d in pool)
    by_skill = Counter(s for d in pool for s in (d.get("skills") or []))
    by_score = Counter(d.get("score", 0) for d in pool)
    return {
        "total": len(pool),
        "by_channel": dict(by_channel.most_common()),
        "by_skill_top": by_skill.most_common(8),
        "by_score": dict(sorted(by_score.items(), reverse=True)),
    }


def _scalar(db: Session, stmt) -> int:
    return int(db.execute(stmt).scalar_one() or 0)
