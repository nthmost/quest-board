"""Display helpers for the real-name / handle identity model."""

from __future__ import annotations


def format_display_name(
    handle: str | None,
    show_real_name: bool | None,
    real_name: str | None,
) -> str:
    """Public display name for a person.

    Just the handle by default (pseudonymous). If the person opted in and has a
    real name that differs from their handle, show "handle (Real Name)".
    """
    handle = (handle or "").strip()
    if show_real_name and real_name:
        real = real_name.strip()
        if real and real.lower() != handle.lower():
            return f"{handle} ({real})"
    return handle
