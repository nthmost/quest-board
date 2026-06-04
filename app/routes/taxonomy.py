"""Taxonomy endpoints: GET /guilds, GET /locations."""

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Guild, Location
from app.schemas.taxonomy import GuildOut, LocationOut

router = APIRouter(tags=["taxonomy"])


@router.get("/guilds", response_model=list[GuildOut])
def list_guilds(db: Session = Depends(get_db)) -> list[GuildOut]:
    rows = db.execute(select(Guild).order_by(Guild.slug)).scalars().all()
    return [GuildOut.model_validate(r) for r in rows]


@router.get("/locations", response_model=list[LocationOut])
def list_locations(db: Session = Depends(get_db)) -> list[LocationOut]:
    rows = db.execute(select(Location).order_by(Location.slug)).scalars().all()
    return [LocationOut.model_validate(r) for r in rows]
