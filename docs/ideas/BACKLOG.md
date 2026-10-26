---
name: backlog
id: backlog
title: Ideas backlog
type: idea
status: exploring
created: 2026-10-26
updated: 2026-10-26
owners: [nthmost]
tags: [backlog, ideas]
---

# Ideas backlog

Every idea we've written about that isn't yet a shipped feature or a committed
decision — raw maybes, designed-but-unbuilt SPEC mechanics, and explicit
out-of-scope-for-v1 items. Each row is a graph node (`type: idea`); promote one
to `docs/proposals/<id>.md` (same `id`) when it's worth a full RFC. Keep
`deferred`/`rejected` rows here with a reason so they don't return as "new."

Source tags in `reason`: SPEC = `SPEC.md`, DEMO = `DEMO.md`. The textual map in
`docs/OVERVIEW.md` lists these grouped by status.

| id | title | status | reason | relates_to |
|---|---|---|---|---|
| boosts-ui | Spend XP to boost a quest | proposed | `quest_boosts` table exists; no UI to spend XP on a boost yet | |
| level-up-ui | Spend XP to level up | proposed | mechanic spec'd; no UI yet | xp-ledger |
| leaderboard | `/leaderboard` top profiles by XP/level | proposed | URL reserved; needs sort + small podium component | |
| per-profile-page | Public `/c/{id}` profile sheet | proposed | URL reserved; stats + current quest + recent events | |
| discord-linking | Link a Discord account to a profile | deferred | `users` carries discord columns; no `/link` slash-command flow | |
| admin-sim-reset | Admin endpoint to wipe simulation state | idea | preserves taxonomy + NPC defs + seed pool | simulator |
| live-sse-feed | Live `/api/v1/feed/stream` | idea | folded into the simulator; split out if it ships earlier | simulator |
| multi-space-vouching | Per-space member vouching | idea | candidate mechanism under personhood-verification | personhood-verification, multi-space |
| graph-basic-auth | HTTP Basic Auth on the feature graph | idea | privacy upgrade if the unadvertised hostname isn't enough | feature-graph |
| backups-automation | Automated `pg_dump` backups on zephyr | idea | not yet wired; needs cron for both `questboard` + `questboard_nb` | two-instance-hosting |
| sub-quests | Nested quests (parent/child, depth, rollup) | proposed | SPEC §1/§4: `parent_quest_id`, `max_depth` (ceiling 3), manual/auto rollup | quest-detail |
| donor-bounties | Donor $ bounties (pledge/collect/withdraw, Stripe) | proposed | SPEC §4: conditional restricted gift to NB, never paid to doers; not built | note-donor-bounties, quest-detail |
| posting-fee-economy | Posting-fee economy (burn vs treasury, refunds) | proposed | SPEC §4: flat/proportional shapes, treasury routing, refund policies | quest-creation, treasury-account |
| claim-reporting | Claim completion reporting (time/notes/photo/state) | proposed | SPEC §4: per-claimer minutes, done_state, notes, photo at `/done` | quest-claim-flow, civic-hours-cert |
| quest-attachments | Photo / media attachments | proposed | SPEC §2 `quest_attachments`; claim photos in v1, quest refs later | claim-reporting |
| level-curves | Configurable level curves (flat/linear/exp/dnd5e/custom) | proposed | SPEC §3: curve config + D&D 5e table | level-up-ui |
| service-principal-api | API keys / service principals (scoped bearer) | proposed | SPEC §5: `api_keys`, scopes, `sp_` tokens | public-api |
| llm-xp-suggestion | LLM XP suggestion at draft (`/quests/draft`) | idea | SPEC §8: calibration-gated, opt-in preview only (not runtime gen) | no-runtime-llm-gen |
| verifier-role | Verifier bonus + verify transition | idea | SPEC: `verifier_bonus_xp`, `POST /verify`, `requires_verification` | quest-verification |
| treasury-account | System treasury account for fees | idea | SPEC §2: singleton `__treasury__` is_system account | posting-fee-economy |
| clone-quest | Clone quest (reopen replacement) | idea | SPEC: `POST /quests/{id}/clone`; no reopen once paid out | quest-claim-flow |
| pdf-certificate | PDF civic-hours certificate renderer | idea | SPEC §4: html works today; pdf deferrable past v1 | civic-hours-cert |
| quest-verification | Re-enable per-quest verification step | deferred | schema column stays; disabled for the demo by decision | quest-claim-flow |
| npc-quest-givers | NPC quest-givers seeding | idea | DEMO: `npc_quest_givers` schema exists, no rows; simulator populates | simulator |
| flavor-text | Per-class flavor text + idle events | idea | DEMO §4/§6: class flavor kits, idle "pauses to refactor a comment" | simulator |
| world-reset | Periodic / admin world reset | idea | DEMO: weekly or on-demand fresh world; preserves class seeds | simulator, admin-sim-reset |
| quest-templates | Slot-filling quest templates | idea | DEMO §3 generator; SPEC §9 lists as out of scope for v1 | discord-data-pipeline |
| xp-decay | XP decay / seasonal resets | deferred | SPEC §9 out of scope for v1 | |
| notifications | Notifications / webhooks | deferred | SPEC §9 out of scope for v1 | |
| fulltext-search | Full-text search (vs ILIKE) | deferred | SPEC §9 out of scope for v1 | quest-browse |
| rate-limits | API rate limiting | deferred | SPEC §9 out of scope for v1 | public-api |
| reputation-badges | Reputation / badges / level names | deferred | SPEC §9 out of scope for v1 (distinct from embeddable badges) | user-page-badges |
| bounty-matching | Bounty matching pledges | deferred | SPEC §9: "match the first $100 on quests tagged X" | donor-bounties |
| bounty-acknowledgment | 501(c)(3) year-end donor letters | deferred | SPEC §9: schema supports; generator deferred | donor-bounties |
| bounty-expiry-sweep | Background bounty-expiry sweep job | deferred | SPEC §9: manual admin endpoint in v1 | donor-bounties |

## Graduation checklist
Promoting a row to a proposal: create `docs/proposals/<id>.md` with frontmatter
(`type: proposal`, a real `status`, any `depends_on`/`relates_to` edges), move
the substance out of this table, then run `python -m scripts.build_docs_index`.
The generated node with the same `id` will win and the row is ignored.
