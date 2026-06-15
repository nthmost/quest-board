"""CSRF protection for cookie-authenticated state-changing requests.

Pattern: synchronizer token tied to the signed session cookie. The token is
generated on first access and stored in the session; templates render it as a
hidden form field; a middleware rejects POST/PUT/DELETE/PATCH that don't
present a matching token.

API routes under /api/v1 are exempt — they're intended for non-cookie clients.
The /login endpoint is exempt too: the user has no established session yet,
and the SessionMiddleware will create one on the GET that renders the form,
so the POST already carries a token by the time we get here. We still exempt
it explicitly to avoid edge cases when a session is missing.

Implementation note: this is a pure ASGI middleware (not BaseHTTPMiddleware)
so that reading the request body here does not consume the stream for
downstream handlers. We buffer the full body, verify the CSRF token from
raw bytes, then pass a replay receive to the inner app.
"""
from __future__ import annotations

import secrets
from typing import Any, Callable
from urllib.parse import parse_qs

from starlette.requests import Request
from starlette.types import ASGIApp, Receive, Scope, Send

from app.errors import render_error_response

SESSION_KEY = "_csrf"
FORM_FIELD = "csrf_token"
HEADER_FIELD = "x-csrf-token"

UNSAFE_METHODS = {"POST", "PUT", "DELETE", "PATCH"}
EXEMPT_PREFIXES = ("/api/v1/",)
EXEMPT_PATHS = {"/login"}


def get_or_create_token(request: Request) -> str:
    token = request.session.get(SESSION_KEY)
    if not token:
        token = secrets.token_urlsafe(32)
        request.session[SESSION_KEY] = token
    return token


def _is_exempt(path: str) -> bool:
    if path in EXEMPT_PATHS:
        return True
    return any(path.startswith(p) for p in EXEMPT_PREFIXES)


def _token_from_body(body: bytes, content_type: str) -> str | None:
    """Extract CSRF token from a pre-read URL-encoded form body."""
    if content_type.startswith("application/x-www-form-urlencoded"):
        params = parse_qs(body.decode("utf-8", errors="replace"))
        values = params.get(FORM_FIELD, [])
        return values[0] if values else None
    return None


async def _read_body(receive: Receive) -> bytes:
    """Drain the ASGI receive stream and return the complete body bytes."""
    body = b""
    more = True
    while more:
        msg = await receive()
        body += msg.get("body", b"")
        more = msg.get("more_body", False)
    return body


class CSRFMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        request = Request(scope, receive=receive)

        if request.method not in UNSAFE_METHODS or _is_exempt(request.url.path):
            await self.app(scope, receive, send)
            return

        # Buffer the entire body so we can (a) read the CSRF token and
        # (b) replay it for the downstream route handler via a fresh receive.
        body = await _read_body(receive)

        expected = request.session.get(SESSION_KEY)
        submitted = request.headers.get(HEADER_FIELD) or _token_from_body(
            body, request.headers.get("content-type", "")
        )

        if not expected or not submitted or not secrets.compare_digest(
            expected, submitted
        ):
            response = render_error_response(
                request, 403, detail="CSRF token missing or invalid"
            )
            await response(scope, receive, send)
            return

        # Replay the buffered body so the inner app can read form fields normally.
        replayed = False

        async def replay_receive() -> dict[str, Any]:
            nonlocal replayed
            if not replayed:
                replayed = True
                return {"type": "http.request", "body": body, "more_body": False}
            return await receive()

        await self.app(scope, replay_receive, send)
