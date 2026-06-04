"""Server-rendered HTML pages for the demo UI.

Currently a single landing page (`/`) that demonstrates the aesthetic against
real seeded data plus a hand-crafted demo character (the characters table is
not yet built). Iterating on layout/feel before the live simulation comes in.
"""

from pathlib import Path

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.auth import current_username, effective_admin, is_admin, is_pretending_user
from app.config import load_economy
from app.db import get_db
from app.models import Character, Guild, Location, Quest, QuestClaim, User, XpTransaction
from app.services import quest_actions
from app.services.levels import cost_to_next_level, xp_progress_pct
from app.services.quest_browse import browse as browse_quests
from app.services.quest_browse import distinct_skills, list_filter_options
from app.services.quest_recommendations import recommend
from app.services.quest_detail import get_detail as get_quest_detail
from app.services.quest_creation_gate import check as check_creation_gate

TEMPLATE_DIR = Path(__file__).resolve().parent.parent / "templates"
templates = Jinja2Templates(directory=str(TEMPLATE_DIR))

router = APIRouter(tags=["pages"])


@router.get("/", response_class=HTMLResponse)
def landing(request: Request, db: Session = Depends(get_db)) -> HTMLResponse:
    username = current_username(request)
    character = None
    char_obj = None
    recommended = []
    guilds_by_id: dict[int, str] = {}
    if username:
        user = _get_user(db, username)
        if user:
            char_obj = _active_character_or_fallback(db, user)
            if char_obj:
                character = _shape_character(db, char_obj)
                recommended = recommend(db, char_obj, limit=8)
                guild_rows = db.execute(select(Guild.id, Guild.name)).all()
                guilds_by_id = {row[0]: row[1] for row in guild_rows}
    return templates.TemplateResponse(
        request,
        "index.html",
        {
            "character": character,
            "quests": _open_quests(db),
            "recommended": recommended,
            "guilds_by_id": guilds_by_id,
            "feed": _real_feed(db),
            "stats": _world_stats(db),
            "current_user": username,
            "is_admin": effective_admin(request, username),
            "actually_admin": is_admin(username),
            "pretending": is_pretending_user(request) and is_admin(username),
        },
    )


@router.get("/quests", response_class=HTMLResponse)
def quests_browse(
    request: Request,
    db: Session = Depends(get_db),
    q: str = "",
    status: str = "",
    guild: str = "",
    location: str = "",
    skill: str = "",
    xp_min: str = "",
    xp_max: str = "",
    urgency: str = "",
    sort: str = "newest",
    page: int = 1,
) -> HTMLResponse:
    xp_min_int = _parse_int(xp_min)
    xp_max_int = _parse_int(xp_max)
    result = browse_quests(
        db,
        q=q.strip(),
        status=status or None,
        guild_slug=guild or None,
        location_slug=location or None,
        skill=skill.strip(),
        xp_min=xp_min_int,
        xp_max=xp_max_int,
        urgency=urgency or None,
        sort=sort,
        page=page,
    )
    options = list_filter_options(db)
    username = current_username(request)
    char = _active_character(db, _get_user(db, username)) if username else None
    eligibility = check_creation_gate(db, username, char)
    return templates.TemplateResponse(
        request,
        "quests_browse.html",
        {
            "result": result,
            "guilds": options["guilds"],
            "locations": options["locations"],
            "skills": distinct_skills(db),
            "current_user": username,
            "is_admin": effective_admin(request, username),
            "actually_admin": is_admin(username),
            "pretending": is_pretending_user(request) and is_admin(username),
            "can_create": eligibility.allowed,
            "create_blocked_reason": eligibility.reason,
        },
    )


@router.get("/quests/new", response_class=HTMLResponse)
def quest_create_form(
    request: Request,
    db: Session = Depends(get_db),
    flash: str = "",
) -> HTMLResponse:
    username = current_username(request)
    if not username:
        return RedirectResponse("/login", status_code=303)
    user = _get_user(db, username)
    char = _active_character(db, user) if user else None
    eligibility = check_creation_gate(db, username, char)
    if not eligibility.allowed:
        return RedirectResponse(f"/quests?flash={eligibility.reason}", status_code=303)
    options = list_filter_options(db)
    fee = _posting_fee()
    return templates.TemplateResponse(
        request, "quest_create.html",
        {
            "current_user": username,
            "is_admin": effective_admin(request, username),
            "character_name": char.name if char else username,
            "character_xp": char.xp_balance if char else 0,
            "posting_fee": fee,
            "guilds": options["guilds"],
            "locations": options["locations"],
            "form": {},
            "flash": flash,
        },
    )


@router.post("/quests/new")
def quest_create_submit(
    request: Request,
    db: Session = Depends(get_db),
    title: str = Form(...),
    description: str = Form(...),
    guild_id: str = Form(""),
    location_id: str = Form(""),
    urgency: str = Form("normal"),
    party_min: str = Form("1"),
    party_max: str = Form(""),
    skills: str = Form(""),
    contact_text: str = Form(""),
    due_date: str = Form(""),
) -> RedirectResponse:
    username = current_username(request)
    if not username:
        return RedirectResponse("/login", status_code=303)
    user = _get_user(db, username)
    char = _active_character(db, user) if user else None
    eligibility = check_creation_gate(db, username, char)
    if not eligibility.allowed:
        return RedirectResponse("/quests", status_code=303)

    from datetime import date
    skill_list = [s.strip() for s in skills.split(",") if s.strip()]
    due = None
    if due_date.strip():
        try:
            due = date.fromisoformat(due_date.strip())
        except ValueError:
            pass

    quest = Quest(
        title=title.strip(),
        description=description.strip(),
        guild_id=_parse_int(guild_id) or None,
        location_id=_parse_int(location_id) or None,
        urgency=urgency if urgency in ("normal", "high") else "normal",
        party_min=max(1, _parse_int(party_min) or 1),
        party_max=_parse_int(party_max) or None,
        skills=skill_list,
        contact_text=contact_text.strip() or None,
        due_date=due,
        creator_user_id=user.id if user else None,
        creator_character_id=char.id if char else None,
        status="open",
    )
    db.add(quest)
    db.flush()

    # Charge posting fee
    fee = _posting_fee()
    if fee > 0 and char is not None:
        quest_actions.charge_posting_fee(db, char, quest, fee)

    db.commit()
    return RedirectResponse(f"/quests/{quest.id}", status_code=303)


@router.get("/quests/{quest_id}", response_class=HTMLResponse)
def quest_detail(
    request: Request,
    quest_id: int,
    db: Session = Depends(get_db),
    flash: str = "",
) -> HTMLResponse:
    username = current_username(request)
    quest = get_quest_detail(db, quest_id, authed=bool(username))
    if quest is None:
        raise HTTPException(status_code=404, detail="quest not found")
    actions = _action_state(db, quest, username)
    can_verify = _can_verify_quest(db, quest, username)
    return templates.TemplateResponse(
        request,
        "quest_detail.html",
        {
            "quest": quest,
            "current_user": username,
            "is_admin": effective_admin(request, username),
            "actually_admin": is_admin(username),
            "pretending": is_pretending_user(request) and is_admin(username),
            "actions": actions,
            "can_verify": can_verify,
            "flash": flash,
        },
    )


@router.post("/quests/{quest_id}/claim")
def quest_claim(
    quest_id: int,
    request: Request,
    db: Session = Depends(get_db),
) -> RedirectResponse:
    return _do_quest_action(quest_id, request, db, "claim")


@router.post("/quests/{quest_id}/release")
def quest_release(
    quest_id: int,
    request: Request,
    db: Session = Depends(get_db),
) -> RedirectResponse:
    return _do_quest_action(quest_id, request, db, "release")


@router.post("/quests/{quest_id}/done")
def quest_done(
    quest_id: int,
    request: Request,
    db: Session = Depends(get_db),
    claim_notes: str = Form(""),
    time_spent_minutes: str = Form(""),
) -> RedirectResponse:
    username = current_username(request)
    if not username:
        return RedirectResponse("/login", status_code=303)
    user = db.execute(select(User).where(User.wiki_username == username)).scalar_one()
    char = _active_character(db, user)
    if char is None:
        return RedirectResponse(
            f"/quests/{quest_id}?flash=No+active+character.", status_code=303,
        )
    minutes = _parse_int(time_spent_minutes)
    flash = ""
    try:
        quest_actions.complete(
            db, char, quest_id,
            done_state="full",
            claim_notes=claim_notes.strip() or None,
            time_spent_minutes=minutes,
        )
    except quest_actions.QuestActionError as e:
        flash = str(e)
    suffix = f"?flash={flash}" if flash else ""
    return RedirectResponse(f"/quests/{quest_id}{suffix}", status_code=303)


@router.post("/quests/{quest_id}/verify")
def quest_verify(
    quest_id: int,
    request: Request,
    db: Session = Depends(get_db),
) -> RedirectResponse:
    username = current_username(request)
    if not username:
        return RedirectResponse("/login", status_code=303)
    user = db.execute(select(User).where(User.wiki_username == username)).scalar_one()
    flash = ""
    try:
        quest_actions.verify(db, user.id, quest_id, is_admin=is_admin(username))
    except quest_actions.QuestActionError as e:
        flash = str(e)
    suffix = f"?flash={flash}" if flash else ""
    return RedirectResponse(f"/quests/{quest_id}{suffix}", status_code=303)


def _do_quest_action(
    quest_id: int, request: Request, db: Session, kind: str,
) -> RedirectResponse:
    username = current_username(request)
    if not username:
        return RedirectResponse("/login", status_code=303)
    user = db.execute(select(User).where(User.wiki_username == username)).scalar_one()
    char = _active_character(db, user)
    if char is None:
        return RedirectResponse(
            f"/quests/{quest_id}?flash=No+active+character.",
            status_code=303,
        )
    fn = quest_actions.claim if kind == "claim" else quest_actions.release
    flash = ""
    try:
        fn(db, char, quest_id)
    except quest_actions.QuestActionError as e:
        flash = str(e)
    suffix = f"?flash={flash}" if flash else ""
    return RedirectResponse(f"/quests/{quest_id}{suffix}", status_code=303)


def _active_character(db: Session, user: User) -> Character | None:
    if user.active_character_id is None:
        return None
    return db.execute(
        select(Character).where(
            Character.id == user.active_character_id,
            Character.deleted_at.is_(None),
        )
    ).scalar_one_or_none()


def _get_user(db: Session, username: str | None) -> User | None:
    if not username:
        return None
    return db.execute(select(User).where(User.wiki_username == username)).scalar_one_or_none()


def _posting_fee() -> int:
    cfg = load_economy().get("xp", {}).get("posting_fee", {})
    if not cfg.get("enabled"):
        return 0
    return cfg.get("flat_amount") or 0


def _action_state(db: Session, quest: dict, username: str | None) -> dict:
    """Compute claimable/releasable for the current viewer's active character."""
    out = {"can_claim": False, "can_release": False, "can_done": False, "character_name": None,
           "no_character": False}
    if not username:
        return out
    user = db.execute(
        select(User).where(User.wiki_username == username)
    ).scalar_one_or_none()
    if user is None:
        return out
    char = _active_character(db, user)
    if char is None:
        out["no_character"] = True
        return out
    out["character_name"] = char.name
    if quest["status"] not in ("open", "claimed") or quest["paid_out_at"]:
        return out
    has_claim = quest_actions.has_active_claim(db, char.id, quest["id"])
    if has_claim:
        out["can_release"] = True
        out["can_done"] = True
        return out
    if (
        quest["party_max"] is not None
        and quest["claims"]["active_count"] >= quest["party_max"]
    ):
        return out  # full party
    out["can_claim"] = True
    return out


def _can_verify_quest(db: Session, quest: dict, username: str | None) -> bool:
    """True when the logged-in user is authorized to verify this done quest."""
    if not username or quest["status"] != "done" or quest.get("paid_out_at"):
        return False
    if is_admin(username):
        return True
    user = db.execute(select(User).where(User.wiki_username == username)).scalar_one_or_none()
    if user is None:
        return False
    verifier_ids = quest.get("verifier_user_ids") or []
    if verifier_ids:
        return user.id in verifier_ids
    # Empty list = creator only
    return quest.get("creator_user_id") == user.id


def _parse_int(raw: str) -> int | None:
    try:
        v = int(raw)
        return v if v >= 0 else None
    except (ValueError, TypeError):
        return None


def _featured_character(db: Session, username: str) -> dict | None:
    """Return the user's active character (or fallback) as a render-ready dict."""
    user = db.execute(select(User).where(User.wiki_username == username)).scalar_one_or_none()
    if user is None:
        return None
    char = _active_character_or_fallback(db, user)
    if char is None:
        return None
    return _shape_character(db, char)


def _active_character_or_fallback(db: Session, user: User) -> Character | None:
    """Prefer user.active_character_id; if missing/deleted, fall back to oldest."""
    if user.active_character_id is not None:
        active = db.execute(
            select(Character).where(
                Character.id == user.active_character_id,
                Character.deleted_at.is_(None),
            )
        ).scalar_one_or_none()
        if active is not None:
            return active
    return db.execute(
        select(Character)
        .where(Character.user_id == user.id, Character.deleted_at.is_(None))
        .order_by(Character.created_at.asc())
        .limit(1)
    ).scalar_one_or_none()


def _shape_character(db: Session, char: Character) -> dict:
    return {
        "name": char.name,
        "class_name": char.class_slug,
        "level": char.level,
        "xp": char.xp_balance,
        "total_xp": char.total_xp_earned,
        "next_level_cost": cost_to_next_level(char.level),
        "xp_percent": xp_progress_pct(char.level, char.total_xp_earned),
        "quests_done": _completion_count(db, char.id),
        "guild": _guild_name(db, char.primary_guild_id),
        "current_action": "RESTING",
        "current_target": "(no quest claimed)",
        "task_label": "IDLE",
        "task_percent": 0,
    }


def _completion_count(db: Session, character_id: int) -> int:
    stmt = (
        select(func.count())
        .select_from(XpTransaction)
        .where(
            XpTransaction.character_id == character_id,
            XpTransaction.reason == "quest_completion",
        )
    )
    return int(db.execute(stmt).scalar_one() or 0)


def _guild_name(db: Session, guild_id: int | None) -> str:
    if guild_id is None:
        return "—"
    return db.execute(select(Guild.name).where(Guild.id == guild_id)).scalar_one_or_none() or "—"


def _open_quests(db: Session) -> list[dict]:
    stmt = (
        select(
            Quest,
            Guild.slug.label("guild_slug"),
            Location.slug.label("location_slug"),
        )
        .outerjoin(Guild, Guild.id == Quest.guild_id)
        .outerjoin(Location, Location.id == Quest.location_id)
        .where(Quest.deleted_at.is_(None), Quest.status == "open")
        .order_by(Quest.created_at.desc())
        .limit(20)
    )
    return [_quest_row(row) for row in db.execute(stmt).all()]


def _quest_row(row) -> dict:
    quest, guild_slug, location_slug = row
    return {
        "id": quest.id,
        "title": quest.title,
        "xp": quest.xp,
        "guild_slug": guild_slug,
        "location_slug": location_slug,
        "urgency": quest.urgency,
        "party_min": quest.party_min,
        "party_max": quest.party_max,
    }


def _real_feed(db: Session, limit: int = 30) -> list[dict]:
    events: list[dict] = []

    # Quest postings
    post_rows = db.execute(
        select(
            Quest.id, Quest.title, Quest.created_at, Quest.creator_attribution,
            Character.name.label("char_name"),
            User.wiki_username.label("user_name"),
        )
        .outerjoin(Character, Character.id == Quest.creator_character_id)
        .outerjoin(User, User.id == Quest.creator_user_id)
        .where(Quest.deleted_at.is_(None))
        .order_by(Quest.created_at.desc())
        .limit(limit)
    ).all()
    for r in post_rows:
        who = r.creator_attribution or r.char_name or r.user_name or "UNKNOWN"
        events.append(_ev(r.created_at, "post", who.upper(), "posted", r.title))

    # Quest claims and completions
    claim_rows = db.execute(
        select(
            QuestClaim.claimed_at, QuestClaim.done_state, QuestClaim.reported_at,
            Character.name.label("char_name"),
            Quest.title, Quest.xp,
        )
        .join(Character, Character.id == QuestClaim.character_id)
        .join(Quest, Quest.id == QuestClaim.quest_id)
        .where(Quest.deleted_at.is_(None))
        .order_by(QuestClaim.claimed_at.desc())
        .limit(limit)
    ).all()
    for r in claim_rows:
        if r.done_state:
            ts = r.reported_at or r.claimed_at
            events.append(_ev(ts, "done", r.char_name.upper(), "completed", r.title, xp=r.xp))
        events.append(_ev(r.claimed_at, "claim", r.char_name.upper(), "claimed", r.title))

    events.sort(key=lambda e: e["_ts"], reverse=True)
    return events[:limit]


def _ev(
    ts, type_: str, who: str, verb: str,
    target: str | None, xp: int | None = None,
) -> dict:
    from datetime import date, timezone
    today = date.today()
    if hasattr(ts, "date"):
        ts_utc = ts.astimezone(timezone.utc) if ts.tzinfo else ts.replace(tzinfo=timezone.utc)
        ts_str = ts_utc.strftime("%H:%M") if ts_utc.date() == today else ts_utc.strftime("%m-%d %H:%M")
    else:
        ts_str = str(ts)
    return {"_ts": ts, "ts": ts_str, "type": type_, "who": who, "verb": verb, "target": target, "xp": xp}


def _world_stats(db: Session) -> dict:
    user_q = select(func.count()).select_from(User).where(User.is_system.is_(False))
    quest_q = select(func.count()).select_from(Quest).where(Quest.deleted_at.is_(None))
    minted_q = select(func.coalesce(func.sum(XpTransaction.amount), 0)).where(
        XpTransaction.amount > 0
    )
    return {
        "user_count": _count(db, user_q),
        "quest_count": _count(db, quest_q),
        "total_xp_minted": _count(db, minted_q),
        "calibration_status": "BOOTSTRAP",
    }


def _count(db: Session, stmt) -> int:
    return int(db.execute(stmt).scalar_one())
