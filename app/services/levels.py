"""Level-curve math driven by economy.yaml's `levels` block.

cost_to_next_level(N) → XP needed to advance from level N to level N+1
under the configured curve. Supported curve names: flat, linear,
exponential, dnd5e, custom. See SPEC.md §3.
"""

from __future__ import annotations

import math

from app.config import load_economy

# Cumulative XP at each D&D 5e level (level 1 = 0 XP, level 20 = 355000).
DND5E_TABLE = [
    0, 300, 900, 2700, 6500, 14000, 23000, 34000, 48000, 64000,
    85000, 100000, 120000, 140000, 165000, 195000, 225000, 265000, 305000, 355000,
]


def level_for_xp(total_xp: int) -> int:
    """Derive level from total accumulated XP. XP is permanent — never spent."""
    cfg = load_economy().get("levels", {})
    max_level = int(cfg.get("max_level", 20))
    level = 1
    while level < max_level:
        if total_xp < _cumulative_threshold(cfg, level + 1):
            break
        level += 1
    return level


def cost_to_next_level(level: int) -> int:
    """XP needed in the current level band to advance to level + 1."""
    cfg = load_economy().get("levels", {})
    max_level = int(cfg.get("max_level", 20))
    if level >= max_level:
        return 0
    return _cumulative_threshold(cfg, level + 1) - _cumulative_threshold(cfg, level)


def xp_progress_pct(level: int, xp_balance: int) -> int:
    """Progress within the current level band, as a percentage."""
    cfg = load_economy().get("levels", {})
    floor = _cumulative_threshold(cfg, level)
    band = cost_to_next_level(level)
    if band <= 0:
        return 100
    pct = round((xp_balance - floor) / band * 100)
    return max(0, min(100, pct))


def _cumulative_threshold(cfg: dict, level: int) -> int:
    """Total XP required to reach `level` from level 1."""
    if level <= 1:
        return 0
    return sum(_curve_dispatch(cfg, lv) for lv in range(1, level))


def _curve_dispatch(cfg: dict, level: int) -> int:
    name = cfg.get("curve", "flat")
    handlers = {
        "flat":        _flat,
        "linear":      _linear,
        "exponential": _exponential,
        "dnd5e":       _dnd5e,
        "custom":      _custom,
    }
    handler = handlers.get(name, _flat)
    return handler(cfg, level)


def _flat(cfg: dict, _level: int) -> int:
    return int(cfg.get("flat", {}).get("cost", 50))


def _linear(cfg: dict, level: int) -> int:
    base = int(cfg.get("linear", {}).get("base", 10))
    return base * level


def _exponential(cfg: dict, level: int) -> int:
    base = int(cfg.get("exponential", {}).get("base", 10))
    return base * (2 ** (level - 1))


def _dnd5e(cfg: dict, level: int) -> int:
    scale = float(cfg.get("dnd5e", {}).get("scale", 1.0))
    if level < 1 or level >= len(DND5E_TABLE):
        return 0
    diff = DND5E_TABLE[level] - DND5E_TABLE[level - 1]
    return max(1, math.ceil(diff * scale))


def _custom(cfg: dict, level: int) -> int:
    costs = cfg.get("custom", {}).get("costs", []) or []
    idx = level - 1
    if idx < 0 or idx >= len(costs):
        return 0
    return int(costs[idx])
