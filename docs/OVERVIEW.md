# Actropolis — design map (text)

_Generated from `docs/index.json` by `scripts/build_docs_index.py`. 67 nodes, 64 edges. A textual companion to the feature graph — same data, grouped as an outline._

## Shipped features (16)

- **Admin console (dashboard, quests, users, templates)** (`admin-console`) · _shipped_ — `/admin/*`, allow-list in economy YAML, SIGHUP reload
- **Discord mining → curate → tag → ingest** (`discord-data-pipeline`) · _shipped_ — one-shot offline prep producing 348 skill-tagged seeds  ↳ relates_to no-runtime-llm-gen
- **Economy config in YAML with SIGHUP hot-reload** (`economy-yaml`) · _shipped_ — single `economy.yaml` source of truth; no settings UI or table  ↳ relates_to admin-console
- **Design-docs feature graph (viewer + index + published site)** (`feature-graph`) · _shipped_ — this graph; `graph.html` + `index.json` live at graph.actropolis.org  ↳ relates_to docs-convention
- **Front page (world stats, featured profile, open quests, live-ish feed)** (`front-page`) · _shipped_ — `/` with `_real_feed` (real recent activity, not a mock)
- **Username / visible-name / real-name identity split** (`identity-names`) · _shipped_ — login vs public display vs private real name + `show_real_name`  ↳ relates_to one-profile-per-account
- **Multiple makerspaces (spaces, primary space, quest scoping)** (`multi-space`) · _shipped_ — migration 0009; Noisebridge, Sequoia Fabrica, OpenCircuit SF, Omni Commons
- **Public read API `/api/v1`** (`public-api`) · _shipped_ — healthz/version/economy/stats/guilds/locations/quests
- **Quest browse — search, filter, sort, paginate** (`quest-browse`) · _shipped_ — `/quests`; ~348 ingested quests in the pool
- **Claim / release / done / verify state machine** (`quest-claim-flow`) · _shipped_ — party_min/max, terminal-status + double-claim guards
- **Human quest posting + eligibility gate** (`quest-creation`) · _shipped_ — `/quests/new`; gate = admin / allowlist / `min_quests_completed`
- **Quest detail page** (`quest-detail`) · _shipped_ — `/quests/{id}` — task panel, claims, boosts, sidebar
- **Reference taxonomy** (`taxonomy`) · _shipped_ — seeded: 17 guilds, 22 locations, 7 character classes
- **One codebase, two branded instances on zephyr** (`two-instance-hosting`) · _shipped_ — `SITE_NAME`/`THEME`; questboard :8080 + questboard-nb :8081
- **Admin "view as user" toggle** (`view-as-user`) · _shipped_ — preview the public UI from an admin account
- **XP ledger + levels on the profile** (`xp-ledger`) · _shipped_ — `xp_transactions`, `total_xp_earned`; welcome grant at signup

## Decisions (3)

### shipped (2)

- **Local accounts instead of wiki SSO** (`local-auth`)  ↳ relates_to spec; relates_to civic-hours-cert
- **One profile per account (both modes)** (`one-profile-per-account`)  ↳ relates_to spec; relates_to demo

### accepted (1)

- **No runtime LLM quest generation** (`no-runtime-llm-gen`)  ↳ relates_to demo

## Proposals (4)

### accepted (1)

- **Progress-Quest simulator (tick loop + SSE feed)** (`simulator`)  ↳ depends_on no-runtime-llm-gen; relates_to spec; realizes demo

### proposed (1)

- **Embeddable user-page badges** (`user-page-badges`)  ↳ relates_to spec

### exploring (1)

- **Personhood verification for local accounts** (`personhood-verification`)  ↳ blocks civic-hours-cert; relates_to local-auth

### deferred (1)

- **Civic-hours certificate** (`civic-hours-cert`) — self-serve local signup removed the in-person personhood guarantee the certificate relied on  ↳ depends_on personhood-verification; relates_to spec; relates_to local-auth; relates_to note-donor-bounties

## Ideas (36)

### proposed (11)

- **Spend XP to boost a quest** (`boosts-ui`) — `quest_boosts` table exists; no UI to spend XP on a boost yet
- **Claim completion reporting (time/notes/photo/state)** (`claim-reporting`) — SPEC §4: per-claimer minutes, done_state, notes, photo at `/done`  ↳ relates_to quest-claim-flow; relates_to civic-hours-cert
- **Donor $ bounties (pledge/collect/withdraw, Stripe)** (`donor-bounties`) — SPEC §4: conditional restricted gift to NB, never paid to doers; not built  ↳ relates_to note-donor-bounties; relates_to quest-detail
- **`/leaderboard` top profiles by XP/level** (`leaderboard`) — URL reserved; needs sort + small podium component
- **Configurable level curves (flat/linear/exp/dnd5e/custom)** (`level-curves`) — SPEC §3: curve config + D&D 5e table  ↳ relates_to level-up-ui
- **Spend XP to level up** (`level-up-ui`) — mechanic spec'd; no UI yet  ↳ relates_to xp-ledger
- **Public `/c/{id}` profile sheet** (`per-profile-page`) — URL reserved; stats + current quest + recent events
- **Posting-fee economy (burn vs treasury, refunds)** (`posting-fee-economy`) — SPEC §4: flat/proportional shapes, treasury routing, refund policies  ↳ relates_to quest-creation; relates_to treasury-account
- **Photo / media attachments** (`quest-attachments`) — SPEC §2 `quest_attachments`; claim photos in v1, quest refs later  ↳ relates_to claim-reporting
- **API keys / service principals (scoped bearer)** (`service-principal-api`) — SPEC §5: `api_keys`, scopes, `sp_` tokens  ↳ relates_to public-api
- **Nested quests (parent/child, depth, rollup)** (`sub-quests`) — SPEC §1/§4: `parent_quest_id`, `max_depth` (ceiling 3), manual/auto rollup  ↳ relates_to quest-detail

### exploring (1)

- **Ideas backlog** (`backlog`)

### idea (14)

- **Admin endpoint to wipe simulation state** (`admin-sim-reset`) — preserves taxonomy + NPC defs + seed pool  ↳ relates_to simulator
- **Automated `pg_dump` backups on zephyr** (`backups-automation`) — not yet wired; needs cron for both `questboard` + `questboard_nb`  ↳ relates_to two-instance-hosting
- **Clone quest (reopen replacement)** (`clone-quest`) — SPEC: `POST /quests/{id}/clone`; no reopen once paid out  ↳ relates_to quest-claim-flow
- **Per-class flavor text + idle events** (`flavor-text`) — DEMO §4/§6: class flavor kits, idle "pauses to refactor a comment"  ↳ relates_to simulator
- **HTTP Basic Auth on the feature graph** (`graph-basic-auth`) — privacy upgrade if the unadvertised hostname isn't enough  ↳ relates_to feature-graph
- **Live `/api/v1/feed/stream`** (`live-sse-feed`) — folded into the simulator; split out if it ships earlier  ↳ relates_to simulator
- **LLM XP suggestion at draft (`/quests/draft`)** (`llm-xp-suggestion`) — SPEC §8: calibration-gated, opt-in preview only (not runtime gen)  ↳ relates_to no-runtime-llm-gen
- **Per-space member vouching** (`multi-space-vouching`) — candidate mechanism under personhood-verification  ↳ relates_to personhood-verification; relates_to multi-space
- **NPC quest-givers seeding** (`npc-quest-givers`) — DEMO: `npc_quest_givers` schema exists, no rows; simulator populates  ↳ relates_to simulator
- **PDF civic-hours certificate renderer** (`pdf-certificate`) — SPEC §4: html works today; pdf deferrable past v1  ↳ relates_to civic-hours-cert
- **Slot-filling quest templates** (`quest-templates`) — DEMO §3 generator; SPEC §9 lists as out of scope for v1  ↳ relates_to discord-data-pipeline
- **System treasury account for fees** (`treasury-account`) — SPEC §2: singleton `__treasury__` is_system account  ↳ relates_to posting-fee-economy
- **Verifier bonus + verify transition** (`verifier-role`) — SPEC: `verifier_bonus_xp`, `POST /verify`, `requires_verification`  ↳ relates_to quest-verification
- **Periodic / admin world reset** (`world-reset`) — DEMO: weekly or on-demand fresh world; preserves class seeds  ↳ relates_to simulator; relates_to admin-sim-reset

### deferred (10)

- **501(c)(3) year-end donor letters** (`bounty-acknowledgment`) — SPEC §9: schema supports; generator deferred  ↳ relates_to donor-bounties
- **Background bounty-expiry sweep job** (`bounty-expiry-sweep`) — SPEC §9: manual admin endpoint in v1  ↳ relates_to donor-bounties
- **Bounty matching pledges** (`bounty-matching`) — SPEC §9: "match the first $100 on quests tagged X"  ↳ relates_to donor-bounties
- **Link a Discord account to a profile** (`discord-linking`) — `users` carries discord columns; no `/link` slash-command flow
- **Full-text search (vs ILIKE)** (`fulltext-search`) — SPEC §9 out of scope for v1  ↳ relates_to quest-browse
- **Notifications / webhooks** (`notifications`) — SPEC §9 out of scope for v1
- **Re-enable per-quest verification step** (`quest-verification`) — schema column stays; disabled for the demo by decision  ↳ relates_to quest-claim-flow
- **API rate limiting** (`rate-limits`) — SPEC §9 out of scope for v1  ↳ relates_to public-api
- **Reputation / badges / level names** (`reputation-badges`) — SPEC §9 out of scope for v1 (distinct from embeddable badges)  ↳ relates_to user-page-badges
- **XP decay / seasonal resets** (`xp-decay`) — SPEC §9 out of scope for v1

## Specs (2)

### accepted (1)

- **Actropolis — API spec (long-term design)** (`spec`)  ↳ relates_to demo

### building (1)

- **Quest Board — Progress Quest demo (delta on spec)** (`demo`)  ↳ relates_to spec

## Reference docs (4)

- **Design-docs information architecture** (`docs-convention`) · _shipped_
- **Shipped features registry** (`features`) · _shipped_
- **Actropolis — project overview** (`overview`) · _shipped_  ↳ relates_to spec; relates_to demo; relates_to ui-reference; relates_to docs-convention
- **Quest Board — UI reference** (`ui-reference`) · _shipped_  ↳ relates_to spec

## Notes (2)

### exploring (1)

- **Actropolis test personas** (`test-personas`)  ↳ relates_to spec

### superseded (1)

- **Design notes — donor bounties + claim reporting** (`note-donor-bounties`) — retained rationale; donor-bounty economics merged into SPEC, and its civic-hours personhood premise was superseded by local-auth — forward design now lives in civic-hours-cert  ↳ superseded_by civic-hours-cert; superseded_by spec; relates_to local-auth
