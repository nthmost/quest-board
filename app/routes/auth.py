"""Wiki login routes: GET /login (form), POST /login (verify), POST /logout."""

from pathlib import Path

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.auth import current_username, login_user, logout_user, upsert_user
from app.db import get_db
from app.wiki_api import verify_login

TEMPLATE_DIR = Path(__file__).resolve().parent.parent / "templates"
templates = Jinja2Templates(directory=str(TEMPLATE_DIR))

router = APIRouter(tags=["auth"])


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
    ok, reason, canonical = verify_login(username.strip(), password)
    if not ok:
        return _render_login(request, error=_describe_failure(reason))
    upsert_user(db, canonical)
    login_user(request, canonical)
    return RedirectResponse("/", status_code=303)


@router.post("/logout")
def logout(request: Request) -> RedirectResponse:
    logout_user(request)
    return RedirectResponse("/", status_code=303)


def _render_login(request: Request, error: str | None) -> HTMLResponse:
    return templates.TemplateResponse(
        request, "login.html", {"error": error}
    )


def _describe_failure(reason: str) -> str:
    """Translate a few MediaWiki failure codes into something user-readable."""
    pretty = {
        "Failed": "Wrong username or password.",
        "WrongPass": "Wrong password.",
        "NotExists": "No such wiki user.",
        "Throttled": "Too many attempts; try again in a minute.",
    }
    return pretty.get(reason, f"Login failed: {reason}")
