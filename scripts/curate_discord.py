"""LLM curation pass over discord_mined.yaml.

Sends each candidate to an OpenAI-compatible chat completions endpoint and
asks "is this a real Noisebridge task ask, and if so, write me a clean quest
title + description + xp + urgency". Filters out non-tasks, sorts by score,
keeps the top N (default 200).

Usage:
    python scripts/curate_discord.py
        [--in data/quest_templates/discord_mined.yaml]
        [--out data/quest_templates/discord_curated.yaml]
        [--target 200]
        [--router http://localhost:4000/v1]
        [--models gpt-4o-mini]
        [--batch 5] [--workers 4]

Environment overrides:
    QUESTBOARD_LLM_ROUTER   default router base URL
    QUESTBOARD_LLM_MODELS   comma-separated model rotation
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path

import httpx
import yaml

DEFAULT_IN = Path("data/quest_templates/discord_mined.yaml")
DEFAULT_OUT = Path("data/quest_templates/discord_curated.yaml")
DEFAULT_ROUTER = os.environ.get("QUESTBOARD_LLM_ROUTER", "http://localhost:4000/v1")
# Comma-separated; batches round-robin across these. Pick a single model class
# so output style stays roughly uniform.
DEFAULT_MODELS = os.environ.get("QUESTBOARD_LLM_MODELS", "gpt-4o-mini")

SYSTEM_PROMPT = """You are filtering Discord messages from the Noisebridge \
hackerspace to find real task asks suitable for a quest board.

For each input message, return a JSON object with these fields:
  id          string  (echo the input id verbatim)
  is_task     bool    (true if it's a concrete, do-able ask; false if it's chat,
                       agreement, joke, generic question, or info-only)
  score       int 1-10 (quality of the ask: 1=barely a task, 10=clear and
                       interesting). Required when is_task=true; use 0 otherwise.
  title       string  (≤80 chars, action-shaped, e.g. "Tighten the dish-rack
                       screws". Required when is_task=true; "" otherwise.)
  description string  (≤200 chars, 1-2 sentences, neutral plain English.
                       Strip Discord cruft like [#channel] / [link]. Required
                       when is_task=true; "" otherwise.)
  xp          int 1-30 (effort estimate; small chores=2-5, mid jobs=8-15,
                       big projects=20-30). Required when is_task=true.
  urgency     "low"|"normal"|"high". Default "normal".

Be strict. Conversations, jokes, "thanks!", "yeah me too", agreements, generic
questions ("does anyone know X?" without a doable verb), and meta posts about
how the channel works are all is_task=false.

Output ONLY a JSON array of objects, one per input. No prose, no code fences."""

USER_TEMPLATE = """Classify these messages. Output a JSON array of {n} objects.

{items}"""


def main() -> int:
    args = _parse_args()
    candidates = _load_candidates(Path(args.input))
    if args.exclude_yaml:
        candidates = _exclude_ids(candidates, Path(args.exclude_yaml))
    if args.limit:
        candidates = candidates[: args.limit]
    print(f"loaded {len(candidates)} candidates", file=sys.stderr)

    results = _curate_all(candidates, args)
    print(f"got {len(results)} model responses", file=sys.stderr)

    kept = _filter_and_rank(candidates, results, args.target)
    print(f"keeping top {len(kept)}", file=sys.stderr)

    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    Path(args.output).write_text(_to_yaml(kept))
    print(f"wrote {args.output}", file=sys.stderr)
    return 0


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser()
    p.add_argument("--input", default=str(DEFAULT_IN))
    p.add_argument("--output", default=str(DEFAULT_OUT))
    p.add_argument("--router", default=DEFAULT_ROUTER)
    p.add_argument("--models", default=DEFAULT_MODELS,
                   help="comma-separated model ids; batches round-robin across them")
    p.add_argument("--batch", type=int, default=5)
    p.add_argument("--workers", type=int, default=6)
    p.add_argument("--target", type=int, default=200)
    p.add_argument("--limit", type=int, default=0,
                   help="cap input candidates (0 = no cap; useful for dry runs)")
    p.add_argument("--exclude-yaml", default="",
                   help="yaml file whose entries' ids should be skipped (for top-ups)")
    p.add_argument("--timeout", type=float, default=120.0)
    return p.parse_args()


def _load_candidates(path: Path) -> list[dict]:
    return yaml.safe_load(path.read_text())


def _exclude_ids(candidates: list[dict], exclude_path: Path) -> list[dict]:
    """Drop candidates whose `id` appears in the excluded yaml."""
    if not exclude_path.exists():
        return candidates
    excluded = {str(d["id"]) for d in yaml.safe_load(exclude_path.read_text()) if d.get("id")}
    print(f"excluding {len(excluded)} ids from {exclude_path}", file=sys.stderr)
    return [c for c in candidates if str(c["id"]) not in excluded]


def _curate_all(candidates: list[dict], args: argparse.Namespace) -> dict[str, dict]:
    """Returns id → judgment dict. Batches round-robin across configured models."""
    batches = list(_chunk(candidates, args.batch))
    models = [m.strip() for m in args.models.split(",") if m.strip()]
    print(f"models in rotation: {models}", file=sys.stderr)
    assignments = [(b, models[i % len(models)]) for i, b in enumerate(batches)]
    judgments: dict[str, dict] = {}
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futs = {
            pool.submit(_judge_batch, batch, model, args): i
            for i, (batch, model) in enumerate(assignments)
        }
        for done, fut in enumerate(as_completed(futs), start=1):
            for j in fut.result():
                judgments[j["id"]] = j
            if done % 5 == 0 or done == len(assignments):
                print(f"  batch {done}/{len(assignments)} done", file=sys.stderr)
    return judgments


def _chunk(items: list, n: int):
    for i in range(0, len(items), n):
        yield items[i : i + n]


def _judge_batch(batch: list[dict], model: str, args: argparse.Namespace) -> list[dict]:
    payload = _build_payload(batch, model)
    try:
        return _call_and_parse(payload, args.router, args.timeout, batch)
    except Exception as e:  # noqa: BLE001 — log and continue, don't kill the whole pass
        print(f"  batch failed ({len(batch)} items, model={model}): {e}", file=sys.stderr)
        return []


def _build_payload(batch: list[dict], model: str) -> dict:
    items_text = "\n".join(_render_item(c) for c in batch)
    user = USER_TEMPLATE.format(n=len(batch), items=items_text)
    return {
        "model": model,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user},
        ],
        "temperature": 0.2,
        "max_tokens": 1500,
    }


def _render_item(c: dict) -> str:
    return f"id={c['id']} | channel={c['channel']} | text={c['raw'][:500]}"


def _call_and_parse(payload: dict, router: str, timeout: float, batch: list[dict]) -> list[dict]:
    with httpx.Client(timeout=timeout) as client:
        resp = client.post(f"{router}/chat/completions", json=payload)
        resp.raise_for_status()
        body = resp.json()
    text = body["choices"][0]["message"]["content"]
    return _parse_json_array(text, batch)


def _parse_json_array(text: str, batch: list[dict]) -> list[dict]:
    """Tolerant JSON-array extractor; handles fenced code, prose preamble."""
    stripped = _strip_code_fence(text)
    match = re.search(r"\[.*\]", stripped, re.DOTALL)
    if not match:
        raise ValueError(f"no JSON array in response: {stripped[:200]!r}")
    parsed = json.loads(match.group(0))
    return [_coerce_judgment(j, batch) for j in parsed]


def _strip_code_fence(text: str) -> str:
    return re.sub(r"^```(?:json)?\s*|\s*```$", "", text.strip(), flags=re.MULTILINE)


def _coerce_judgment(j: dict, batch: list[dict]) -> dict:
    """Force expected types, defaulting missing fields conservatively."""
    return {
        "id": str(j.get("id", "")),
        "is_task": bool(j.get("is_task", False)),
        "score": int(j.get("score", 0) or 0),
        "title": str(j.get("title", "") or "")[:80],
        "description": str(j.get("description", "") or "")[:200],
        "xp": int(j.get("xp", 0) or 0),
        "urgency": _normalize_urgency(j.get("urgency", "normal")),
    }


def _normalize_urgency(value) -> str:
    s = str(value or "normal").strip().lower()
    return s if s in {"low", "normal", "high"} else "normal"


def _filter_and_rank(
    candidates: list[dict], judgments: dict[str, dict], target: int
) -> list[dict]:
    """Combine source rows with judgments; keep top N by score."""
    keepers = [m for c in candidates if (m := _merge(c, judgments.get(c["id"])))]
    keepers.sort(key=lambda e: (e["score"], e["channel"] == "help-wanted"), reverse=True)
    return keepers[:target]


def _merge(c: dict, j: dict | None) -> dict | None:
    if not j or not j.get("is_task"):
        return None
    return {
        "id": c["id"],
        "source": c["source"],
        "channel": c["channel"],
        "guild_slug": c["guild_slug"],
        "posted_at": c["posted_at"],
        "author": c.get("author", ""),
        "title": j["title"] or c.get("title_seed", ""),
        "description": j["description"] or c["raw"][:200],
        "xp": j["xp"] if j["xp"] > 0 else 5,
        "urgency": j["urgency"],
        "score": j["score"],
        "raw": c["raw"],
    }


def _to_yaml(items: list[dict]) -> str:
    header = (
        "# LLM-curated quest seeds, mined from NB Discord and scored.\n"
        "# Top entries by score; review before promoting to live pool.\n"
        f"# Generated: {datetime.now().isoformat(timespec='seconds')}\n\n"
    )
    return header + yaml.safe_dump(items, sort_keys=False, allow_unicode=True, width=100)


if __name__ == "__main__":
    sys.exit(main())
