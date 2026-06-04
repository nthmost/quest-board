"""Mine NB Discord archives for messages that read like quest requests.

Target channels: help-wanted, facilities, fabrication-n-lasers, woodshop,
electronics, safety-council. Output a YAML pool of cleaned candidate quests
for hand-review before they land in the live `quest_templates` table.

Usage:
    python scripts/mine_discord.py
        [--out data/quest_templates/discord_mined.yaml]
        [--archive /path/to/discord-archive]

Set NBQUEST_DISCORD_ARCHIVE to point at a DiscordChatExporter-style folder
tree of `<id>______<channel-name>/*.json` exports.

Heuristic, not LLM. The output file is meant to be reviewed by a human
before going anywhere near production.
"""

from __future__ import annotations

import argparse
import json
import os
import re
from datetime import datetime
from pathlib import Path

import yaml

DEFAULT_ARCHIVE = Path(
    os.environ.get("NBQUEST_DISCORD_ARCHIVE", "./discord-archive")
).expanduser()
DEFAULT_OUT = Path("data/quest_templates/discord_mined.yaml")

# Channel-folder substring → (human channel name, guild slug).
# Substring match is enough because folder names are like
# "1501005354077782218______help-wanted". Order matters: more specific
# substrings should come before more generic ones (e.g. wiki-docs-wg
# before any 'wiki' fallback).
TARGETS: dict[str, tuple[str, str]] = {
    # General help / infrastructure
    "help-wanted":              ("help-wanted",              "metaguild"),
    "facilities":               ("facilities",               "facilities"),
    "nb-home-assistant":        ("nb-home-assistant",        "rack"),
    # Workshops
    "woodshop-wall":            ("woodshop-wall",            "woodshop"),
    "woodshop":                 ("woodshop",                 "woodshop"),
    "electronics":              ("electronics",              "electronics"),
    "fabrication":              ("fabrication-n-lasers",     "laser-cutter"),
    "laser-trainers":           ("laser-trainers",           "laser-cutter"),
    "3d-printing":              ("3d-printing",              "3d-printing"),
    "sewing":                   ("sewing",                   "sewing"),
    # Org / process
    "safety-council":           ("safety-council",           "safety"),
    "secretary-guild-private":  ("secretary-guild-private",  "secretary"),
    "donations":                ("donations",                "treasurer"),
    "wiki-docs-wg":             ("wiki-docs-wg",             "writing"),
    # Software / AI
    "ai-ml":                    ("ai-ml",                    "ai-ml"),
    "python":                   ("python",                   "ai-ml"),
    # Creative / events
    "writing":                  ("writing",                  "writing"),
    "zine":                     ("zine",                     "writing"),
    "games":                    ("games",                    "gaming"),
    "philosophy":               ("philosophy",               "philosophy"),
    "spacebridge":              ("spacebridge",              "spacebridge"),
}

STRONG_REQUEST = re.compile(
    r"\b("
    r"looking for|need(s|ed)? help|need(s|ed)? to|need(s|ed)? a|"
    r"would (someone|anyone|you|love|appreciate)|"
    r"could (someone|anyone|you|i|we)|"
    r"can (someone|anyone)|"
    r"if (someone|anyone|you|i)|"
    r"anyone (have|know|got|here|interested|willing|want|able|free)|"
    r"who (has|knows|wants|can|could|would)|"
    r"is (anyone|someone|there) (here|able|interested|free|around)|"
    r"requesting|seeking|please|takers|volunteers"
    r")\b",
    re.IGNORECASE,
)
TASK_VERB = re.compile(
    r"\b("
    r"build|install|repair|fix|clean|sort|organize|organise|tidy|"
    r"donate|bring|find|teach|trained|train|set ?up|label|tighten|"
    r"move|return|convert|gather|test|check|inspect|sweep|vacuum|"
    r"replace|patch|paint|wire|solder|cut|drill|mount|hang|"
    r"document|write up|wiki|post|update|catalogue|inventory|"
    r"pick up|drop off|fetch|borrow|loan|loaning|lend"
    r")\b",
    re.IGNORECASE,
)
EMOJI_OPENER = re.compile(r"^\s*[\U0001F300-\U0001FAFF☀-➿✂📺🎹📝☎🛠]")
DISCORD_MENTION = re.compile(r"<[#@!&][!&]?\d+>")
DISCORD_EMOJI = re.compile(r"<a?:[a-zA-Z0-9_]+:\d+>")
URL_PATTERN = re.compile(r"https?://\S+")
WHITESPACE = re.compile(r"\s+")

MIN_LEN = 40
MAX_LEN = 700  # truncate long tirades; demo wants compact quests
MAX_PER_CHANNEL = 80  # keep review tractable

# Authors known to be bots / not human posters.
SKIP_AUTHORS: set[str] = {"NoiseBot", "MEE6", "Carl-bot"}


def main() -> None:
    args = _parse_args()
    archive = Path(args.archive).expanduser()
    out = Path(args.out)
    if not archive.exists():
        raise SystemExit(f"archive not found: {archive}")

    target_dirs = _find_target_channels(archive)
    print(f"matched {len(target_dirs)} channels")
    candidates = _gather_all(target_dirs)
    print(f"{len(candidates)} candidate messages after filtering")

    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(_to_yaml(candidates))
    print(f"wrote {out}")


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser()
    p.add_argument("--archive", default=str(DEFAULT_ARCHIVE))
    p.add_argument("--out", default=str(DEFAULT_OUT))
    return p.parse_args()


def _find_target_channels(archive: Path) -> list[tuple[Path, str, str]]:
    """Return [(channel_dir, channel_name, guild_slug), ...] for requested targets."""
    channels_dir = archive / "channels"
    out: list[tuple[Path, str, str]] = []
    for sub in channels_dir.iterdir():
        if not sub.is_dir():
            continue
        match = _match_target(sub.name)
        if match is None:
            continue
        out.append((sub, match[0], match[1]))
    return out


def _match_target(folder_name: str) -> tuple[str, str] | None:
    """Resolve a folder name to (channel_name, guild_slug) by substring match."""
    lower = folder_name.lower()
    for key, value in TARGETS.items():
        if key in lower:
            return value
    return None


def _gather_all(targets: list[tuple[Path, str, str]]) -> list[dict]:
    candidates: list[dict] = []
    for chan_dir, chan_name, guild_slug in targets:
        candidates.extend(_gather_channel(chan_dir, chan_name, guild_slug))
    return _dedupe_by_id(candidates)


def _dedupe_by_id(items: list[dict]) -> list[dict]:
    """Keep first occurrence per id; source archives sometimes contain duplicates."""
    seen: set[str] = set()
    out: list[dict] = []
    for item in items:
        key = item["id"]
        if key in seen:
            continue
        seen.add(key)
        out.append(item)
    return out


def _gather_channel(chan_dir: Path, chan_name: str, guild_slug: str) -> list[dict]:
    msgs_path = chan_dir / "messages.json"
    if not msgs_path.exists():
        return []
    raw = json.loads(msgs_path.read_text())
    candidates = [c for m in raw if (c := _shape_candidate(m, chan_name, guild_slug))]
    if len(candidates) <= MAX_PER_CHANNEL:
        return candidates
    return _sample_evenly(candidates, MAX_PER_CHANNEL)


def _sample_evenly(items: list[dict], target: int) -> list[dict]:
    """Take `target` items spread evenly across the input — keeps a wide time range."""
    step = len(items) / target
    return [items[int(i * step)] for i in range(target)]


def _shape_candidate(msg: dict, chan_name: str, guild_slug: str) -> dict | None:
    if not _passes_filter(msg, chan_name):
        return None
    cleaned = _clean(msg.get("content", ""))
    if len(cleaned) < MIN_LEN:
        return None
    return {
        "id": str(msg.get("id", "")),
        "source": f"discord:{chan_name}",
        "guild_slug": guild_slug,
        "channel": chan_name,
        "author": msg.get("author_display_name") or msg.get("author_name") or "",
        "posted_at": _normalize_ts(msg.get("created_at", "")),
        "title_seed": _title_seed(cleaned),
        "raw": cleaned[:MAX_LEN],
    }


VALID_TYPES = {None, "default", "reply", "MessageType.default", "MessageType.reply"}


def _passes_filter(msg: dict, channel: str) -> bool:
    """Drop replies, system messages, bot posts, URL-only, and non-task chatter."""
    if msg.get("reference"):
        return False
    if msg.get("type") not in VALID_TYPES:
        return False
    if msg.get("author_name") in SKIP_AUTHORS:
        return False
    content = msg.get("content", "") or ""
    if not content.strip():
        return False
    if channel == "help-wanted":
        return _passes_help_wanted(content)
    return _passes_chat_channel(content)


def _passes_help_wanted(content: str) -> bool:
    """help-wanted is curated: emoji opener OR an explicit request phrase counts."""
    if EMOJI_OPENER.match(content):
        return True
    return bool(STRONG_REQUEST.search(content))


def _passes_chat_channel(content: str) -> bool:
    """Chat channels are noisy: require both a request phrase AND a task verb."""
    return bool(STRONG_REQUEST.search(content) and TASK_VERB.search(content))


def _clean(content: str) -> str:
    """Strip Discord cruft: channel/user mentions, custom emoji, raw URLs, whitespace."""
    s = DISCORD_MENTION.sub("[#channel]", content)
    s = DISCORD_EMOJI.sub("", s)
    s = URL_PATTERN.sub("[link]", s)
    s = WHITESPACE.sub(" ", s).strip()
    return s


def _title_seed(text: str) -> str:
    """First sentence or first 90 chars, whichever is shorter."""
    first_sentence = re.split(r"(?<=[.!?])\s", text, maxsplit=1)[0]
    seed = first_sentence if len(first_sentence) < 90 else text[:90]
    return seed.strip().rstrip(".!?,;:")


def _normalize_ts(ts: str) -> str:
    if not ts:
        return ""
    # Discord exports give ISO 8601 with offset; normalize to date-only for output sanity.
    try:
        return datetime.fromisoformat(ts.replace("Z", "+00:00")).date().isoformat()
    except ValueError:
        return ts


def _to_yaml(candidates: list[dict]) -> str:
    header = (
        "# Mined Discord candidates. Each entry is a draft quest_template seed.\n"
        "# Review each by hand before promoting to the live pool.\n"
        f"# Generated: {datetime.now().isoformat(timespec='seconds')}\n\n"
    )
    return header + yaml.safe_dump(candidates, sort_keys=False, allow_unicode=True, width=100)


if __name__ == "__main__":
    main()
