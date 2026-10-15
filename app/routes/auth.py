"""Independent auth routes: GET/POST /login, GET/POST /register, POST /logout."""

from datetime import UTC, datetime
from pathlib import Path

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.auth import (
    current_username,
    get_user_by_username,
    login_user,
    logout_user,
    register_user,
    username_taken,
)
from app.db import get_db
from app.local_auth import (
    normalize_username,
    validate_password,
    validate_username,
    verify_password,
)

TEMPLATE_DIR = Path(__file__).resolve().parent.parent / "templates"
templates = Jinja2Templates(directory=str(TEMPLATE_DIR))

router = APIRouter(tags=["auth"])


# ── Login ────────────────────────────────────────────────────────────────
@router.get("/login", response_class=HTMLResponse)
def login_form(request: Request) -> HTMLResponse:
    if current_username(request):
        return RedirectResponse("/", status_code=303)
    return _render_login(request, error=None)


@router.post("/login", response_class=HTMLResponse)
def login_submit(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db),
) -> HTMLResponse:
    username = normalize_username(username)
    user = get_user_by_username(db, username)
    if user is None or not verify_password(user.password_hash, password):
        return _render_login(request, error="Wrong username or password.")
    user.last_seen_at = datetime.now(UTC)
    db.commit()
    # Log in under the stored (canonical-cased) username.
    login_user(request, user.wiki_username)
    return RedirectResponse("/", status_code=303)


# ── Register ─────────────────────────────────────────────────────────────
@router.get("/register", response_class=HTMLResponse)
def register_form(request: Request) -> HTMLResponse:
    if current_username(request):
        return RedirectResponse("/", status_code=303)
    return _render_register(request, error=None, username="")


@router.post("/register", response_class=HTMLResponse)
def register_submit(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    password2: str = Form(""),
    db: Session = Depends(get_db),
) -> HTMLResponse:
    username = normalize_username(username)

    err = validate_username(username)
    if err:
        return _render_register(request, error=err, username=username)
    err = validate_password(password)
    if err:
        return _render_register(request, error=err, username=username)
    if password2 and password != password2:
        return _render_register(request, error="Passwords don't match.", username=username)
    if username_taken(db, username):
        return _render_register(request, error="That username is taken.", username=username)

    user = register_user(db, username, password)
    login_user(request, user.wiki_username)
    # New accounts have no character yet — send them straight to make one.
    return RedirectResponse("/me/characters/new", status_code=303)


# ── Logout ───────────────────────────────────────────────────────────────
@router.post("/logout")
def logout(request: Request) -> RedirectResponse:
    logout_user(request)
    return RedirectResponse("/", status_code=303)


# ── Renderers ────────────────────────────────────────────────────────────
def _render_login(request: Request, error: str | None) -> HTMLResponse:
    return templates.TemplateResponse(request, "login.html", {"error": error})


def _render_register(request: Request, error: str | None, username: str) -> HTMLResponse:
    return templates.TemplateResponse(
        request, "register.html", {"error": error, "username": username}
    )
