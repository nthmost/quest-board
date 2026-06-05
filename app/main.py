"""FastAPI app factory and SIGHUP handler for hot-reloading economy.yaml."""

import os
import signal
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware

from app import __version__
from app.config import reload_economy
from app.csrf import CSRFMiddleware, get_or_create_token
from app.errors import install_error_handlers
from app.routes import admin, auth, me, meta, pages, quests, taxonomy

STATIC_DIR = Path(__file__).resolve().parent / "static"
SESSION_MAX_AGE_SECONDS = 60 * 60 * 24 * 14  # 14 days


def _compute_asset_version() -> str:
    """Use the latest CSS mtime so cache busts whenever we ship style changes."""
    css = STATIC_DIR / "css" / "nes.css"
    return str(int(css.stat().st_mtime)) if css.exists() else __version__


ASSET_VERSION = _compute_asset_version()


def create_app() -> FastAPI:
    app = FastAPI(
        title="Noisebridge Quest Board",
        version=__version__,
        docs_url="/api/v1/docs",
        openapi_url="/api/v1/openapi.json",
    )
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
    _install_template_globals(app)
    app.add_middleware(CSRFMiddleware)
    _install_session_middleware(app)
    _mount_routers(app)
    install_error_handlers(app)
    _install_sighup_handler()
    return app


def _install_template_globals(app: FastAPI) -> None:
    """Inject per-request globals so `{{ request.state.* }}` resolves in templates."""
    @app.middleware("http")
    async def _attach_globals(request: Request, call_next):
        request.state.asset_v = ASSET_VERSION
        request.state.csrf_token = get_or_create_token(request)
        return await call_next(request)


def _install_session_middleware(app: FastAPI) -> None:
    """Signed-cookie sessions. Secret comes from SESSION_SECRET env."""
    secret = os.environ.get("SESSION_SECRET")
    if not secret:
        raise RuntimeError("SESSION_SECRET is required")
    app.add_middleware(
        SessionMiddleware,
        secret_key=secret,
        max_age=SESSION_MAX_AGE_SECONDS,
        same_site="lax",
        https_only=True,
    )


def _mount_routers(app: FastAPI) -> None:
    app.include_router(meta.router, prefix="/api/v1")
    app.include_router(taxonomy.router, prefix="/api/v1")
    app.include_router(quests.router, prefix="/api/v1")
    app.include_router(auth.router)
    app.include_router(admin.router)
    app.include_router(me.router)
    app.include_router(pages.router)


def _install_sighup_handler() -> None:
    """Reload economy YAML on SIGHUP without restarting the process."""
    signal.signal(signal.SIGHUP, _on_sighup)


def _on_sighup(_signum: int, _frame) -> None:
    reload_economy()


app = create_app()
