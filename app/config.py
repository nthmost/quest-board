"""Configuration: environment variables for runtime, YAML for economy rules."""

import os
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

ECONOMY_YAML_DEFAULT = "/etc/questboard/economy.yaml"
ECONOMY_YAML_DEV_FALLBACK = "economy.example.yaml"


def get_database_url() -> str:
    """Read DATABASE_URL from env. Required."""
    url = os.environ.get("DATABASE_URL")
    if not url:
        raise RuntimeError("DATABASE_URL is required")
    return url


def get_economy_yaml_path() -> Path:
    """Resolve the YAML path: ECONOMY_YAML_PATH env wins, then default, then dev fallback."""
    explicit = os.environ.get("ECONOMY_YAML_PATH")
    if explicit:
        return Path(explicit)
    if Path(ECONOMY_YAML_DEFAULT).exists():
        return Path(ECONOMY_YAML_DEFAULT)
    return Path(ECONOMY_YAML_DEV_FALLBACK)


@lru_cache(maxsize=1)
def load_economy() -> dict[str, Any]:
    """Load and cache the economy YAML. Cleared by reload_economy() on SIGHUP."""
    path = get_economy_yaml_path()
    with path.open() as f:
        return yaml.safe_load(f)


def reload_economy() -> dict[str, Any]:
    """Force-reload the YAML. Called from SIGHUP handler."""
    load_economy.cache_clear()
    return load_economy()


def get_public_economy() -> dict[str, Any]:
    """Subset of economy YAML safe to expose on GET /economy."""
    cfg = load_economy()
    return {
        "xp": _public_xp(cfg.get("xp", {})),
        "levels": cfg.get("levels", {}),
        "quests": cfg.get("quests", {}),
        "leaderboard": cfg.get("leaderboard", {}),
    }


def _public_xp(xp_cfg: dict[str, Any]) -> dict[str, Any]:
    """Strip nothing for now; all xp config is public-safe."""
    return xp_cfg
