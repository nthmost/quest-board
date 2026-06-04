"""Opaque cursor encoding for paginated lists. Cursor = base64(created_at_iso|id)."""

import base64
from datetime import datetime


def encode_cursor(created_at: datetime, row_id: int) -> str:
    """Pack a (created_at, id) tuple into a URL-safe opaque token."""
    payload = f"{created_at.isoformat()}|{row_id}"
    return base64.urlsafe_b64encode(payload.encode()).decode().rstrip("=")


def decode_cursor(token: str) -> tuple[datetime, int]:
    """Unpack a cursor. Raises ValueError on garbage."""
    padded = token + "=" * (-len(token) % 4)
    payload = base64.urlsafe_b64decode(padded.encode()).decode()
    iso, row_id = payload.split("|", 1)
    return datetime.fromisoformat(iso), int(row_id)
