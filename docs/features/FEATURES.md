---
id: features
title: Shipped features registry
type: reference
status: shipped
created: 2026-10-26
updated: 2026-10-26
owners: [nthmost]
tags: [features, registry]
---

# Shipped features registry

Implemented capabilities, as lightweight graph nodes. The table's first column
`id` keys each node; `scripts/build_docs_index.py` ingests these rows as
`type: feature` nodes. Anything with real design tension gets promoted to a
`decisions/` or `proposals/` file (which then wins the id); this table is the
home for the "it's built, here it is" facts that would otherwise only live in
prose in SPEC/UI/STATUS.

| id | title | status | reason | relates_to |
|---|---|---|---|---|
| front-page | Front page (world stats, featured profile, open quests, live-ish feed) | shipped | `/` with `_real_feed` (real recent activity, not a mock) | |
| quest-browse | Quest browse — search, filter, sort, paginate | shipped | `/quests`; ~348 ingested quests in the pool | |
| quest-detail | Quest detail page | shipped | `/quests/{id}` — task panel, claims, boosts, sidebar | |
| quest-claim-flow | Claim / release / done / verify state machine | shipped | party_min/max, terminal-status + double-claim guards | |
| quest-creation | Human quest posting + eligibility gate | shipped | `/quests/new`; gate = admin / allowlist / `min_quests_completed` | |
| multi-space | Multiple makerspaces (spaces, primary space, quest scoping) | shipped | migration 0009; Noisebridge, Sequoia Fabrica, OpenCircuit SF, Omni Commons | |
| identity-names | Username / visible-name / real-name identity split | shipped | login vs public display vs private real name + `show_real_name` | one-profile-per-account |
| xp-ledger | XP ledger + levels on the profile | shipped | `xp_transactions`, `total_xp_earned`; welcome grant at signup | |
| admin-console | Admin console (dashboard, quests, users, templates) | shipped | `/admin/*`, allow-list in economy YAML, SIGHUP reload | |
| view-as-user | Admin "view as user" toggle | shipped | preview the public UI from an admin account | |
| public-api | Public read API `/api/v1` | shipped | healthz/version/economy/stats/guilds/locations/quests | |
| taxonomy | Reference taxonomy | shipped | seeded: 17 guilds, 22 locations, 7 character classes | |
| economy-yaml | Economy config in YAML with SIGHUP hot-reload | shipped | single `economy.yaml` source of truth; no settings UI or table | admin-console |
| discord-data-pipeline | Discord mining → curate → tag → ingest | shipped | one-shot offline prep producing 348 skill-tagged seeds | no-runtime-llm-gen |
| two-instance-hosting | One codebase, two branded instances on zephyr | shipped | `SITE_NAME`/`THEME`; questboard :8080 + questboard-nb :8081 | |
| feature-graph | Design-docs feature graph (viewer + index + published site) | shipped | this graph; `graph.html` + `index.json` live at graph.actropolis.org | docs-convention |
