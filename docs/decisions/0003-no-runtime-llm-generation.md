---
id: no-runtime-llm-gen
title: No runtime LLM quest generation
type: decision
status: accepted
created: 2026-05-09
updated: 2026-10-26
owners: [nthmost]
tags: [quests, llm, data-pipeline]
relates_to: [demo]
---

# No runtime LLM quest generation

## Status
Accepted (2026-05-09). Reflected in the shipped quest pool: 348 seeds ingested
once, none generated live.

## Context
An early demo idea had NPC quest-givers call Ollama at runtime to generate fresh
quests for color. That couples the request path to a local model's latency and
output quality, and makes the live world non-deterministic and hard to review.

## Decision
**No LLM calls at runtime.** The LLM is used only **offline, once**, during data
prep — `curate_discord.py` cleans mined Discord messages and `tag_skills.py`
assigns skills. The live `quests` table is seeded from that fixed, human-review-
able pool (`data/quest_templates/discord_tagged.yaml`). NPCs, when the simulator
lands, draw from the seed pool plus hand-curated templates.

## Consequences
- The data pipeline (`mine → curate → tag → ingest`) is repeatable but not part
  of the runtime.
- Any future "fresh quests" feature is a separate proposal, not an implicit
  runtime behavior.
