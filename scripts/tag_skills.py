"""LLM skill-tagging pass over discord_curated.yaml.

Reads the controlled skill vocabulary from data/skill_vocab.yaml, asks the
LiteLLM router to pick 1-3 skills per quest from that vocab. Writes a new
file with each entry's `skills` array filled in.

Usage:
    python scripts/tag_skills.py
        [--in data/quest_templates/discord_curated.yaml]
        [--out data/quest_templates/discord_tagged.yaml]
        [--vocab data/skill_vocab.yaml]
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

DEFAULT_IN = Path("data/quest_templates/discord_curated.yaml")
DEFAULT_OUT = Path("data/quest_templates/discord_tagged.yaml")
DEFAULT_VOCAB = Path("data/skill_vocab.yaml")
# OpenAI-compatible chat completions endpoint (e.g. a LiteLLM router or vLLM).
# Override with QUESTBOARD_LLM_ROUTER / QUESTBOARD_LLM_MODELS env vars.
DEFAULT_ROUTER = os.environ.get("QUESTBOARD_LLM_ROUTER", "http://localhost:4000/v1")
DEFAULT_MODELS = os.environ.get(
    "QUESTBOARD_LLM_MODELS", "gpt-4o-mini"
)

SYSTEM_PROMPT_TEMPLATE = """You tag Noisebridge hackerspace quests with skills.

Pick 1 to 3 skills per quest, ONLY from this controlled list:
{vocab}

Rules:
- Use exact slugs from the list. Do not invent new slugs.
- 1 skill if the task is narrow; 2-3 if it spans areas.
- Prefer the most specific skill that applies (e.g. "soldering" over
  "electronics-debug" when the task is literally soldering).
- Output ONLY a JSON array of {{"id": "...", "skills": ["...", ...]}} objects,
  one per input. No prose, no code fences."""

USER_TEMPLATE = """Tag these {n} quests:

{items}"""


def main() -> int:
    args = _parse_args()
    vocab = _load_vocab(Path(args.vocab))
    quests = _load_quests(Path(args.input))
    print(f"loaded {len(quests)} quests, {len(vocab)} skills in vocab", file=sys.stderr)

    skill_map = _tag_all(quests, vocab, args)
    print(f"got skill tags for {len(skill_map)} quests", file=sys.stderr)

    enriched = [_apply_skills(q, skill_map.get(q["id"], []), vocab) for q in quests]
    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    Path(args.output).write_text(_to_yaml(enriched))
    print(f"wrote {args.output}", file=sys.stderr)
    return 0


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser()
    p.add_argument("--input", default=str(DEFAULT_IN))
    p.add_argument("--output", default=str(DEFAULT_OUT))
    p.add_argument("--vocab", default=str(DEFAULT_VOCAB))
    p.add_argument("--router", default=DEFAULT_ROUTER)
    p.add_argument("--models", default=DEFAULT_MODELS)
    p.add_argument("--batch", type=int, default=10)
    p.add_argument("--workers", type=int, default=9)
    p.add_argument("--timeout", type=float, default=90.0)
    return p.parse_args()


def _load_vocab(path: Path) -> list[str]:
    raw = yaml.safe_load(path.read_text())
    flat: list[str] = []
    for slugs in raw.get("categories", {}).values():
        flat.extend(slugs)
    return flat


def _load_quests(path: Path) -> list[dict]:
    return yaml.safe_load(path.read_text())


def _tag_all(
    quests: list[dict], vocab: list[str], args: argparse.Namespace,
) -> dict[str, list[str]]:
    """Returns id → list[skill_slug]."""
    batches = list(_chunk(quests, args.batch))
    models = [m.strip() for m in args.models.split(",") if m.strip()]
    print(f"models in rotation: {models}", file=sys.stderr)
    assignments = [(b, models[i % len(models)]) for i, b in enumerate(batches)]

    out: dict[str, list[str]] = {}
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futs = {
            pool.submit(_tag_batch, batch, model, vocab, args): i
            for i, (batch, model) in enumerate(assignments)
        }
        for done, fut in enumerate(as_completed(futs), start=1):
            for j in fut.result():
                out[j["id"]] = j["skills"]
            if done % 3 == 0 or done == len(assignments):
                print(f"  batch {done}/{len(assignments)} done", file=sys.stderr)
    return out


def _chunk(items: list, n: int):
    for i in range(0, len(items), n):
        yield items[i : i + n]


def _tag_batch(
    batch: list[dict], model: str, vocab: list[str], args: argparse.Namespace
) -> list[dict]:
    payload = _build_payload(batch, model, vocab)
    try:
        return _call_and_parse(payload, args.router, args.timeout)
    except Exception as e:  # noqa: BLE001
        print(f"  batch failed ({len(batch)} items, model={model}): {e}", file=sys.stderr)
        return []


def _build_payload(batch: list[dict], model: str, vocab: list[str]) -> dict:
    system = SYSTEM_PROMPT_TEMPLATE.format(vocab=", ".join(vocab))
    items_text = "\n".join(_render_item(q) for q in batch)
    user = USER_TEMPLATE.format(n=len(batch), items=items_text)
    return {
        "model": model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "temperature": 0.1,
        "max_tokens": 800,
    }


def _render_item(q: dict) -> str:
    return f"id={q['id']} | title={q['title']} | desc={q.get('description', '')}"


def _call_and_parse(payload: dict, router: str, timeout: float) -> list[dict]:
    with httpx.Client(timeout=timeout) as client:
        resp = client.post(f"{router}/chat/completions", json=payload)
        resp.raise_for_status()
        body = resp.json()
    text = body["choices"][0]["message"]["content"]
    return _parse_json_array(text)


def _parse_json_array(text: str) -> list[dict]:
    stripped = re.sub(r"^```(?:json)?\s*|\s*```$", "", text.strip(), flags=re.MULTILINE)
    match = re.search(r"\[.*\]", stripped, re.DOTALL)
    if not match:
        raise ValueError(f"no JSON array in response: {stripped[:200]!r}")
    parsed = json.loads(match.group(0))
    return [_coerce(j) for j in parsed]


def _coerce(j: dict) -> dict:
    return {
        "id": str(j.get("id", "")),
        "skills": [str(s) for s in (j.get("skills") or []) if s],
    }


def _apply_skills(quest: dict, skills: list[str], vocab: list[str]) -> dict:
    """Filter to vocab-only, dedupe, cap at 3, attach to quest dict."""
    valid = list(dict.fromkeys(s for s in skills if s in vocab))[:3]
    return {**quest, "skills": valid}


def _to_yaml(items: list[dict]) -> str:
    header = (
        "# Discord-mined quests, LLM-curated and skill-tagged against skill_vocab.yaml.\n"
        "# Each entry has skills: [...] (1-3 tags from the controlled vocab).\n"
        f"# Generated: {datetime.now().isoformat(timespec='seconds')}\n\n"
    )
    return header + yaml.safe_dump(items, sort_keys=False, allow_unicode=True, width=100)


if __name__ == "__main__":
    sys.exit(main())
