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
    normalize_real_name,
    normalize_username,
    validate_password,
    validate_real_name,
    validate_username,
    verify_password,
)
from app.services import characters as characters_svc

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
    handle: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db),
) -> HTMLResponse:
    handle = normalize_username(handle)
    user = get_user_by_username(db, handle)
    if user is None or not verify_password(user.password_hash, password):
        return _render_login(request, error="Wrong handle or password.")
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
    return _render_register(request, error=None, handle="", real_name="")


@router.post("/register", response_class=HTMLResponse)
def register_submit(
    request: Request,
    real_name: str = Form(...),
    handle: str = Form(...),
    password: str = Form(...),
    password2: str = Form(""),
    db: Session = Depends(get_db),
) -> HTMLResponse:
    real_name = normalize_real_name(real_name)
    handle = normalize_username(handle)

    def fail(msg: str) -> HTMLResponse:
        return _render_register(request, error=msg, handle=handle, real_name=real_name)

    err = validate_real_name(real_name)
    if err:
        return fail(err)
    err = validate_username(handle)
    if err:
        return fail(err)
    err = validate_password(password)
    if err:
        return fail(err)
    if password2 and password != password2:
        return fail("Passwords don't match.")
    if username_taken(db, handle):
        return fail("That handle is taken.")

    user = register_user(db, handle, password, real_name=real_name)
    # Fold profile creation into signup: one handle-named profile, random class.
    characters_svc.create_default_profile(db, user.id, handle)
    login_user(request, user.wiki_username)
    return RedirectResponse("/", status_code=303)


# ── Logout ───────────────────────────────────────────────────────────────
@router.post("/logout")
def logout(request: Request) -> RedirectResponse:
    logout_user(request)
    return RedirectResponse("/", status_code=303)


# ── Renderers ────────────────────────────────────────────────────────────
def _render_login(request: Request, error: str | None) -> HTMLResponse:
    return templates.TemplateResponse(request, "login.html", {"error": error})


def _render_register(
    request: Request, error: str | None, handle: str, real_name: str
) -> HTMLResponse:
    return templates.TemplateResponse(
        request, "register.html",
        {"error": error, "handle": handle, "real_name": real_name},
    )
