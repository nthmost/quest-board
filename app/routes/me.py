"""Self-service routes for the logged-in user: list / create / delete characters."""

import contextlib
from pathlib import Path

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import (
    current_username,
    is_admin,
    is_pretending_user,
    require_login,
    set_pretend_user,
)
from app.db import get_db
from app.models import Guild, User
from app.services import characters as characters_svc

TEMPLATE_DIR = Path(__file__).resolve().parent.parent / "templates"
templates = Jinja2Templates(directory=str(TEMPLATE_DIR))

router = APIRouter(prefix="/me", tags=["me"])


@router.get("/characters", response_class=HTMLResponse)
def list_characters(
    request: Request,
    username: str = Depends(require_login),
    db: Session = Depends(get_db),
) -> HTMLResponse:
    user = _user_or_die(db, username)
    rows = characters_svc.list_for_user(db, user.id)
    return templates.TemplateResponse(
        request, "me_characters.html",
        {
            "current_user": username,
            "characters": _decorate_characters(db, rows, user.active_character_id),
            "active_id": user.active_character_id,
            "max_chars": characters_svc.max_characters_per_user(),
            "actually_admin": is_admin(username),
            "pretending": is_pretending_user(request) and is_admin(username),
        },
    )


@router.get("/characters/new", response_class=HTMLResponse)
def new_character_form(
    request: Request,
    username: str = Depends(require_login),
    db: Session = Depends(get_db),
    error: str | None = None,
) -> HTMLResponse:
    user = _user_or_die(db, username)
    cap = characters_svc.max_characters_per_user()
    existing = characters_svc.list_for_user(db, user.id)
    if len(existing) >= cap:
        return RedirectResponse("/me/characters?msg=at_cap", status_code=303)
    return templates.TemplateResponse(
        request, "me_character_new.html",
        {
            "current_user": username,
            "classes": characters_svc.list_classes(db),
            "guilds": characters_svc.list_guilds(db),
            "error": error,
            "form": {"name": "", "class_slug": "", "primary_guild_id": ""},
        },
    )


@router.post("/characters", response_class=HTMLResponse)
def create_character(
    request: Request,
    username: str = Depends(require_login),
    db: Session = Depends(get_db),
    name: str = Form(...),
    class_slug: str = Form(...),
    primary_guild_id: str = Form(""),
) -> HTMLResponse:
    user = _user_or_die(db, username)
    guild_id = int(primary_guild_id) if primary_guild_id else None
    try:
        characters_svc.create_character(db, user.id, name, class_slug, guild_id)
    except characters_svc.CharacterError as e:
        return _re_render_with_error(
            request, username, db, str(e), name, class_slug, primary_guild_id,
        )
    return RedirectResponse("/me/characters", status_code=303)


@router.post("/characters/{character_id}/delete")
def delete_character(
    character_id: int,
    username: str = Depends(require_login),
    db: Session = Depends(get_db),
) -> RedirectResponse:
    user = _user_or_die(db, username)
    # Owner mismatch or already-deleted: treat the slot as freed silently.
    with contextlib.suppress(characters_svc.CharacterError):
        characters_svc.soft_delete(db, user.id, character_id)
    return RedirectResponse("/me/characters", status_code=303)


@router.post("/view-as")
def toggle_view_as(
    request: Request,
    username: str = Depends(require_login),
) -> RedirectResponse:
    """Admins can flip into 'view as user' mode and back. No-op for non-admins."""
    if is_admin(username):
        set_pretend_user(request, on=not is_pretending_user(request))
    target = request.headers.get("referer") or "/"
    return RedirectResponse(target, status_code=303)


@router.post("/characters/{character_id}/activate")
def activate_character(
    character_id: int,
    username: str = Depends(require_login),
    db: Session = Depends(get_db),
) -> RedirectResponse:
    user = _user_or_die(db, username)
    with contextlib.suppress(characters_svc.CharacterError):
        characters_svc.set_active(db, user.id, character_id)
    return RedirectResponse("/me/characters", status_code=303)


def _decorate_characters(db: Session, rows, active_id: int | None) -> list[dict]:
    """Build the id→name map once, then enrich each row with guild_name + is_active."""
    guild_map = {
        g.id: g.name
        for g in db.execute(select(Guild)).scalars().all()
    }
    return [
        {
            "id": c.id,
            "name": c.name,
            "class_slug": c.class_slug,
            "level": c.level,
            "xp_balance": c.xp_balance,
            "created_at": c.created_at,
            "guild_name": guild_map.get(c.primary_guild_id),
            "is_active": c.id == active_id,
        }
        for c in rows
    ]


def _user_or_die(db: Session, username: str) -> User:
    user = db.execute(select(User).where(User.wiki_username == username)).scalar_one()
    return user


def _re_render_with_error(
    request: Request, username: str, db: Session, error: str,
    name: str, class_slug: str, primary_guild_id: str,
) -> HTMLResponse:
    return templates.TemplateResponse(
        request, "me_character_new.html",
        {
            "current_user": current_username(request),
            "classes": characters_svc.list_classes(db),
            "guilds": characters_svc.list_guilds(db),
            "error": error,
            "form": {
                "name": name,
                "class_slug": class_slug,
                "primary_guild_id": primary_guild_id,
            },
        },
    )
