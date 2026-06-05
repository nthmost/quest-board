"""In-universe error pages.

Renders the shared `error.html` template for HTML clients and falls back to
JSON for API clients (any request under /api/v1/). One handler per status
code we care about (404, 403, 405, 500), plus a generic catch-all for any
other uncaught HTTPException.

Flavor copy is intentionally Progress-Quest-shaped: the Quartermaster, the
Board, the ledger.
"""
from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.exceptions import HTTPException
from fastapi.responses import JSONResponse, Response
from fastapi.templating import Jinja2Templates
from starlette.exceptions import HTTPException as StarletteHTTPException

TEMPLATE_DIR = Path(__file__).resolve().parent / "templates"
_templates = Jinja2Templates(directory=str(TEMPLATE_DIR))

# Code → context. `actions` is a list of {label, href} buttons.
_HOME = {"label": "RETURN TO TAVERN", "href": "/"}
_QUESTS = {"label": "VIEW ALL QUESTS", "href": "/quests"}

ERROR_CONTEXTS: dict[int, dict] = {
    404: {
        "heading": "QUEST NOT FOUND",
        "panel_header": "NO SUCH ENTRY IN THE LEDGER",
        "panel_color": "yellow",
        "flavor": (
            "The Quartermaster squints at the page where this quest should be "
            "and finds only blank parchment. Whatever you sought is not here."
        ),
        "actions": [_HOME, _QUESTS],
    },
    403: {
        "heading": "YOUR PARTY LACKS THE SEAL",
        "panel_header": "ACCESS DENIED",
        "panel_color": "red",
        "flavor": (
            "The Board's wardens turn you away. Either your writ of passage "
            "has lapsed, or this hall is reserved for higher-ranking adventurers."
        ),
        "actions": [_HOME],
    },
    405: {
        "heading": "THAT IS NOT HOW IT IS DONE",
        "panel_header": "WRONG INCANTATION",
        "panel_color": "yellow",
        "flavor": (
            "The Quartermaster shakes his head. The motion you have made is "
            "not one this hall recognizes."
        ),
        "actions": [_HOME],
    },
    500: {
        "heading": "THE QUARTERMASTER HAS FAINTED",
        "panel_header": "INTERNAL SERVER ERROR",
        "panel_color": "red",
        "flavor": (
            "The Board cannot process your quest at this time. The barkeep "
            "has been notified and will revive him shortly."
        ),
        "actions": [_HOME],
    },
}


def _is_api(request: Request) -> bool:
    return request.url.path.startswith("/api/")


def render_error_response(
    request: Request,
    status_code: int,
    detail: str | None = None,
) -> Response:
    if _is_api(request):
        return JSONResponse(
            {"error": detail or _default_detail(status_code), "status": status_code},
            status_code=status_code,
        )

    ctx = dict(ERROR_CONTEXTS.get(status_code, ERROR_CONTEXTS[500]))
    ctx["status_code"] = status_code
    if detail and status_code != 500:
        ctx["detail"] = detail
    return _templates.TemplateResponse(
        request, "error.html", ctx, status_code=status_code
    )


def _default_detail(status_code: int) -> str:
    return {
        403: "forbidden",
        404: "not found",
        405: "method not allowed",
        500: "internal server error",
    }.get(status_code, "error")


async def _http_exception_handler(
    request: Request, exc: StarletteHTTPException
) -> Response:
    return render_error_response(request, exc.status_code, detail=str(exc.detail))


async def _unhandled_exception_handler(request: Request, exc: Exception) -> Response:
    return render_error_response(request, 500)


def install_error_handlers(app: FastAPI) -> None:
    app.add_exception_handler(StarletteHTTPException, _http_exception_handler)
    app.add_exception_handler(HTTPException, _http_exception_handler)
    app.add_exception_handler(Exception, _unhandled_exception_handler)
