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
"""
from __future__ import annotations

import secrets

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import PlainTextResponse, Response

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


async def _extract_submitted_token(request: Request) -> str | None:
    header = request.headers.get(HEADER_FIELD)
    if header:
        return header
    ctype = request.headers.get("content-type", "")
    if ctype.startswith("application/x-www-form-urlencoded") or ctype.startswith(
        "multipart/form-data"
    ):
        form = await request.form()
        value = form.get(FORM_FIELD)
        if isinstance(value, str):
            return value
    return None


class CSRFMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        if request.method not in UNSAFE_METHODS or _is_exempt(request.url.path):
            return await call_next(request)

        expected = request.session.get(SESSION_KEY)
        submitted = await _extract_submitted_token(request)
        if not expected or not submitted or not secrets.compare_digest(
            expected, submitted
        ):
            return PlainTextResponse("CSRF token missing or invalid", status_code=403)

        return await call_next(request)
