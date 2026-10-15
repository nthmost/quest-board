#!/usr/bin/env python
"""Set (or create) a user's password — bootstrap admins, reset credentials.

Usage:
    python -m scripts.set_password <username> [password]

If password is omitted, a strong random one is generated and printed once.
Creates the user if they don't exist, otherwise updates the hash in place.
Run with the app's env (DATABASE_URL) available.
"""

from __future__ import annotations

import secrets
import sys
from datetime import UTC, datetime

from app.db import SessionLocal
from app.auth import get_user_by_username
from app.local_auth import hash_password, normalize_username, validate_username
from app.models import User


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print(__doc__)
        return 2

    username = normalize_username(argv[1])
    err = validate_username(username)
    if err:
        print(f"error: {err}", file=sys.stderr)
        return 1

    password = argv[2] if len(argv) > 2 else secrets.token_urlsafe(18)
    generated = len(argv) <= 2

    db = SessionLocal()
    try:
        user = get_user_by_username(db, username)
        if user is None:
            user = User(
                wiki_username=username,
                password_hash=hash_password(password),
                last_seen_at=datetime.now(UTC),
            )
            db.add(user)
            action = "created"
        else:
            user.password_hash = hash_password(password)
            action = "updated"
        db.commit()
    finally:
        db.close()

    print(f"{action} user '{username}'")
    if generated:
        print(f"generated password: {password}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
