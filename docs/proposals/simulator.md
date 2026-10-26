---
id: simulator
title: Progress-Quest simulator (tick loop + SSE feed)
type: proposal
status: accepted
created: 2026-05-08
updated: 2026-10-26
owners: [nthmost]
tags: [demo, simulator, sse]
realizes: [demo]
relates_to: [spec]
depends_on: [no-runtime-llm-gen]
---

# Progress-Quest simulator

## Status
Accepted, **not yet built** — the largest remaining slice of the demo. Design
lives in DEMO.md §6; this node tracks it as a unit of work.

## Summary
An async tick loop (one real second per tick, 30× sim speedup) that advances
`sim_state`, fires NPC quest posts, runs profile auto-claim/auto-complete to
maturity, writes append-only `simulation_events`, and drives a live SSE feed at
`/api/v1/feed/stream`.

## What it unblocks (currently stubbed because the sim doesn't run)
- Live SSE activity feed (the front page renders real recent activity today via
  `_real_feed`, but not a live stream).
- The active profile's "current task" panel (always `RESTING` today).
- NPC quest-giver rows (`npc_quest_givers` table exists, no rows).
- An admin reset endpoint to wipe simulation state.

## Open questions
- Reset cadence (weekly vs admin-on-demand).
- NPC count / personas per guild.
- Whether to run the sim at all on the Noisebridge ("real board") instance — per
  config it should not seed NPCs or run a sim clock.
