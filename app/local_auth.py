"""Independent password auth for Actropolis.

Replaces the old NB-wiki password-proxy. Accounts live in our own `users`
table; passwords are hashed with Argon2id and never stored in plaintext.
"""

from __future__ import annotations

import re

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHash, VerifyMismatchError

_ph = PasswordHasher()

USERNAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9 _-]{1,48}[A-Za-z0-9]$")
MIN_PASSWORD_LEN = 8


def normalize_username(username: str) -> str:
    """Collapse internal whitespace and trim. Display casing is preserved;
    uniqueness is enforced case-insensitively at the query layer."""
    return re.sub(r"\s+", " ", (username or "").strip())


def validate_username(username: str) -> str | None:
    """Return an error string if invalid, else None."""
    if not username:
        return "Pick a username."
    if not USERNAME_RE.match(username):
        return (
            "Usernames are 3–50 characters: letters, numbers, spaces, "
            "hyphens, or underscores (must start and end with a letter or number)."
        )
    return None


def validate_password(password: str) -> str | None:
    """Return an error string if too weak, else None."""
    if not password or len(password) < MIN_PASSWORD_LEN:
        return f"Password must be at least {MIN_PASSWORD_LEN} characters."
    return None


def hash_password(password: str) -> str:
    return _ph.hash(password)


def verify_password(password_hash: str | None, password: str) -> bool:
    """Verify a password against a stored hash. False for missing/invalid hashes."""
    if not password_hash:
        return False
    try:
        return _ph.verify(password_hash, password)
    except (VerifyMismatchError, InvalidHash):
        return False
    except Exception:
        return False


def needs_rehash(password_hash: str) -> bool:
    try:
        return _ph.check_needs_rehash(password_hash)
    except Exception:
        return False
