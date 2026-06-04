"""Schemas for meta/health/stats endpoints."""

from typing import Any

from pydantic import BaseModel


class HealthOut(BaseModel):
    status: str = "ok"


class VersionOut(BaseModel):
    version: str


class StatsOut(BaseModel):
    quest_count: int
    quests_open: int
    quests_done: int
    user_count: int
    total_xp_minted: int
    total_xp_burned: int
    gold_standard_set_size: int
    calibration_status: str
    economy_warnings: list[str]


class EconomyOut(BaseModel):
    config: dict[str, Any]
