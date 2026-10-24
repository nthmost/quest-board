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
from app.local_auth import (
    hash_password,
    normalize_real_name,
    normalize_visible_name,
    validate_password,
    validate_real_name,
    validate_visible_name,
    verify_password,
)
from app.models import Guild, User
from app.services import characters as characters_svc
from app.services import spaces as spaces_svc

TEMPLATE_DIR = Path(__file__).resolve().parent.parent / "templates"
templates = Jinja2Templates(directory=str(TEMPLATE_DIR))

router = APIRouter(prefix="/me", tags=["me"])


@router.get("/characters", response_class=HTMLResponse)
def list_characters(
    request: Request,
    username: str = Depends(require_login),
    db: Session = Depends(get_db),
    msg: str = "",
) -> HTMLResponse:
    user = _user_or_die(db, username)
    rows = characters_svc.list_for_user(db, user.id)
    return templates.TemplateResponse(
        request, "me_characters.html",
        {
            "current_user": username,
            "real_name": user.real_name or "",
            "show_real_name": user.show_real_name,
            "characters": _decorate_characters(db, rows, user.active_character_id),
            "active_id": user.active_character_id,
            "max_chars": characters_svc.max_characters_per_user(),
            "classes": characters_svc.list_classes(db),
            "actually_admin": is_admin(username),
            "pretending": is_pretending_user(request) and is_admin(username),
            "spaces": spaces_svc.list_spaces(db),
            "primary_space_id": user.primary_space_id,
            "primary_space": spaces_svc.get_space(db, user.primary_space_id),
            "msg": msg,
        },
    )


@router.post("/profile")
def update_profile(
    request: Request,
    username: str = Depends(require_login),
    db: Session = Depends(get_db),
    real_name: str = Form(""),
    visible_name: str = Form(""),
    show_real_name: str = Form(""),
    class_slug: str = Form(""),
    primary_space_id: str = Form(""),
) -> RedirectResponse:
    """Update identity: real name, visible name, real-name visibility, class, space.

    The username (login) is fixed and not editable here.
    """
    user = _user_or_die(db, username)

    # Real name (required, unenforced).
    real_name = normalize_real_name(real_name)
    if validate_real_name(real_name):
        return RedirectResponse("/me/characters?msg=real_name_required", status_code=303)
    user.real_name = real_name

    # Real-name visibility toggle (checkbox → bool).
    user.show_real_name = show_real_name.lower() in ("on", "true", "1", "yes")

    # Visible name: freely changeable public display name (no login/session impact).
    visible_name = normalize_visible_name(visible_name)
    if validate_visible_name(visible_name):
        return RedirectResponse("/me/characters?msg=visible_name_invalid", status_code=303)

    # Optional class flavor.
    if class_slug.strip():
        try:
            characters_svc.set_class(db, user.id, class_slug.strip())
        except characters_svc.CharacterError:
            return RedirectResponse("/me/characters?msg=class_invalid", status_code=303)

    # Primary makerspace.
    if primary_space_id.strip():
        space = spaces_svc.get_space(db, _safe_int(primary_space_id))
        user.primary_space_id = space.id if space else None
    else:
        user.primary_space_id = None

    db.commit()
    characters_svc.rename_active(db, user.id, visible_name)
    return RedirectResponse("/me/characters?msg=profile_saved", status_code=303)


@router.post("/password")
def change_password(
    request: Request,
    username: str = Depends(require_login),
    db: Session = Depends(get_db),
    current_password: str = Form(...),
    new_password: str = Form(...),
    new_password2: str = Form(""),
) -> RedirectResponse:
    """Self-serve password change: verify current, set new."""
    user = _user_or_die(db, username)
    if not verify_password(user.password_hash, current_password):
        return RedirectResponse("/me/characters?msg=pw_wrong_current", status_code=303)
    if validate_password(new_password):
        return RedirectResponse("/me/characters?msg=pw_too_short", status_code=303)
    if new_password2 and new_password != new_password2:
        return RedirectResponse("/me/characters?msg=pw_mismatch", status_code=303)
    user.password_hash = hash_password(new_password)
    db.commit()
    return RedirectResponse("/me/characters?msg=pw_changed", status_code=303)


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


def _safe_int(raw: str) -> int | None:
    try:
        return int(raw)
    except (ValueError, TypeError):
        return None


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
