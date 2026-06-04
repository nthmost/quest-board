"""Pydantic schemas for guilds and locations."""

from pydantic import BaseModel, ConfigDict


class GuildOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    slug: str
    name: str
    wiki_url: str | None
    description: str | None


class LocationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    slug: str
    name: str
    kind: str
    description: str | None
