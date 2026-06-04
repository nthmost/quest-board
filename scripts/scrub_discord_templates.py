"""Scrub PII from Discord-mined quest template YAMLs.

Removes:
  - `author` field (real Discord display names)
  - `raw` field (verbatim message text)
  - Entries whose content references safety incidents, harassment, or personal conflict

Rewrites `id` to a stable salted hash so the Discord message pointer is not exposed.
The hash preserves uniqueness for keying without leaking provenance.

Run from repo root:
    python scripts/scrub_discord_templates.py
"""
from __future__ import annotations

import hashlib
import re
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = REPO_ROOT / "data" / "quest_templates"

# Salt is a fixed string baked into the public scrub. It is not a secret; it
# only ensures the hash is not trivially reversible by guessing raw Discord IDs.
SALT = "quest-board-public-2026"

# Drop entries whose content involves safety incidents or personal conflict.
# Operational/admin discussion about safety processes is OK; specific incidents
# and named complaints are not.
DROP_IDS = {
    "1354275466990583888",  # harassment report (names victim, describes incident)
    "1106247138712768694",  # fire exit security detail
}

STRIP_FIELDS = ("author", "raw")


def hash_id(raw_id: str) -> str:
    h = hashlib.sha256(f"{SALT}:{raw_id}".encode()).hexdigest()[:12]
    return f"tpl-{h}"


def scrub_entry(entry: dict) -> dict:
    cleaned = {k: v for k, v in entry.items() if k not in STRIP_FIELDS}
    cleaned["id"] = hash_id(str(entry["id"]))
    return cleaned


def scrub_file(path: Path) -> tuple[int, int]:
    entries = yaml.safe_load(path.read_text()) or []
    kept = [scrub_entry(e) for e in entries if str(e.get("id")) not in DROP_IDS]
    header = ""
    for line in path.read_text().splitlines():
        if line.startswith("#"):
            header += line + "\n"
        else:
            break
    out = header + yaml.safe_dump(kept, sort_keys=False, allow_unicode=True, width=100)
    path.write_text(out)
    return len(entries), len(kept)


def main() -> None:
    for name in ("discord_mined.yaml", "discord_tagged.yaml"):
        path = DATA_DIR / name
        before, after = scrub_file(path)
        print(f"{name}: {before} -> {after} entries (dropped {before - after})")


if __name__ == "__main__":
    main()
