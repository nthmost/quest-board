"""Auth helpers: who's the current user, upsert on first login, route guards."""

from datetime import UTC, datetime

from fastapi import HTTPException, Request
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import load_economy
from app.local_auth import hash_password
from app.models import User

SESSION_KEY = "user"
PRETEND_KEY = "view_as_user"  # admin's "view as user" toggle


def get_user_by_username(db: Session, username: str) -> User | None:
    """Case-insensitive lookup by the stored username."""
    return db.execute(
        select(User).where(func.lower(User.username) == username.lower())
    ).scalar_one_or_none()


def username_taken(db: Session, username: str) -> bool:
    return get_user_by_username(db, username) is not None


def register_user(
    db: Session, username: str, password: str, real_name: str | None = None
) -> User:
    """Create a new account with a hashed password. `username` is the login
    credential; `real_name` is private. Caller must have already validated the
    inputs and confirmed the username is free."""
    user = User(
        username=username,
        real_name=real_name,
        password_hash=hash_password(password),
        last_seen_at=datetime.now(UTC),
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def current_username(request: Request) -> str | None:
    """The wiki username from the signed-cookie session, or None."""
    return request.session.get(SESSION_KEY)


def login_user(request: Request, username: str) -> None:
    """Mark this session as authenticated for `username`."""
    request.session[SESSION_KEY] = username


def logout_user(request: Request) -> None:
    """Drop auth from this session."""
    request.session.pop(SESSION_KEY, None)


def require_login(request: Request) -> str:
    """FastAPI dependency: 401s if not logged in; returns the username if so."""
    username = current_username(request)
    if not username:
        raise HTTPException(status_code=401, detail="login required")
    return username


def is_admin(username: str | None) -> bool:
    """Check the YAML admin allow-list. Case-insensitive. Real admin status,
    ignores any 'view as user' pretend flag."""
    if not username:
        return False
    allowed = load_economy().get("admin", {}).get("usernames", []) or []
    return username.lower() in {a.lower() for a in allowed}


def is_pretending_user(request: Request) -> bool:
    """True when an actual admin has flipped 'view as user' on for this session."""
    return bool(request.session.get(PRETEND_KEY))


def effective_admin(request: Request, username: str | None) -> bool:
    """Admin status as the UI should treat it: true admin AND not pretending."""
    return is_admin(username) and not is_pretending_user(request)


def set_pretend_user(request: Request, on: bool) -> None:
    if on:
        request.session[PRETEND_KEY] = True
    else:
        request.session.pop(PRETEND_KEY, None)


def require_admin(request: Request) -> str:
    """FastAPI dep: 401 if not logged in, 403 if not on the admin allow-list.
    Pretend-mode does NOT lock real admins out of /admin/* — the toggle is
    a UI-rendering hint, not a permission gate."""
    username = require_login(request)
    if not is_admin(username):
        raise HTTPException(status_code=403, detail="admin only")
    return username
