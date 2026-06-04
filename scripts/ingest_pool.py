"""Ingest data/quest_templates/discord_tagged.yaml into the live quests table.

Each entry becomes an open quest with no concrete creator (so it renders
as 'The Quartermaster' on the detail page). Idempotent on title — re-running
skips entries that already exist.

Usage:
    DATABASE_URL=... python scripts/ingest_pool.py
        [--input data/quest_templates/discord_tagged.yaml]
        [--limit N]
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import yaml
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import SessionLocal
from app.models import Guild, Quest

DEFAULT_IN = Path("data/quest_templates/discord_tagged.yaml")


def main() -> int:
    args = _parse_args()
    pool = _load_pool(Path(args.input))
    if args.limit:
        pool = pool[: args.limit]
    print(f"loaded {len(pool)} entries from {args.input}", file=sys.stderr)

    with SessionLocal() as db:
        guild_map = _guild_map(db)
        added, skipped = _ingest(db, pool, guild_map)
        db.commit()
    print(f"added {added} new, skipped {skipped} existing", file=sys.stderr)
    return 0


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser()
    p.add_argument("--input", default=str(DEFAULT_IN))
    p.add_argument("--limit", type=int, default=0)
    return p.parse_args()


def _load_pool(path: Path) -> list[dict]:
    return yaml.safe_load(path.read_text()) or []


def _guild_map(db: Session) -> dict[str, int]:
    return {g.slug: g.id for g in db.execute(select(Guild)).scalars().all()}


def _ingest(db: Session, pool: list[dict], guild_map: dict[str, int]) -> tuple[int, int]:
    existing_titles = _existing_titles(db)
    added = 0
    skipped = 0
    for entry in pool:
        title = entry["title"]
        if title in existing_titles:
            skipped += 1
            continue
        db.add(_build_quest(entry, guild_map))
        existing_titles.add(title)  # avoid dupes within this batch too
        added += 1
    return added, skipped


def _existing_titles(db: Session) -> set[str]:
    return {row[0] for row in db.execute(select(Quest.title)).all()}


def _build_quest(entry: dict, guild_map: dict[str, int]) -> Quest:
    return Quest(
        title=entry["title"],
        description=entry.get("description") or "",
        guild_id=guild_map.get(entry.get("guild_slug")),
        xp=int(entry.get("xp", 5) or 5),
        xp_source="discord_mined",
        urgency=_normalize_urgency(entry.get("urgency", "normal")),
        skills=list(entry.get("skills") or []),
        internal_notes=_provenance_note(entry),
        creator_bonus_xp=0,
        verifier_bonus_xp=0,
        posting_fee_charged=0,
        posting_fee_destination=None,
        party_min=1,
        party_max=None,
        requires_verification=False,
        status="open",
        depth=0,
    )


def _normalize_urgency(value) -> str:
    s = str(value or "normal").strip().lower()
    return s if s in {"low", "normal", "high"} else "normal"


def _provenance_note(entry: dict) -> str | None:
    """Admin-only provenance trail. Lives in internal_notes so it doesn't
    affect the public-facing 'POSTED BY · The Quartermaster' attribution."""
    src = entry.get("source")
    msg_id = entry.get("id")
    author = entry.get("author")
    posted_at = entry.get("posted_at")
    if not src or not msg_id:
        return None
    parts = [f"source: {src}#{msg_id}"]
    if author:
        parts.append(f"original author: {author}")
    if posted_at:
        parts.append(f"original posted: {posted_at}")
    return " · ".join(parts)


if __name__ == "__main__":
    sys.exit(main())
