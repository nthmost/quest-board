# Build Status

Last updated: 2026-05-09. Lives next to the code; update when shipping.

---

## Live and working at <https://nbquest.nthmost.net/>

### Public
- **Front page (`/`)** — world stats, character sheet (real if logged-in &
  has a character; CTA otherwise), open-quest cards, mock activity feed,
  ALL QUESTS / LOG IN nav.
- **All quests (`/quests`)** — full search + filter (text on title and
  description, status, guild, location), 5 sort options, offset
  pagination. 348 quests in the pool. Cards link to detail pages.
- **Quest detail (`/quests/{id}`)** — hero title, status pill, ♦ THE TASK
  panel with description + skill chips, sub-quests panel (when present),
  CLAIMS panel (with claim/release buttons), BOOSTS panel (when present),
  DETAILS sidebar (xp, urgency, party, guild, location, contact,
  sign-off), POSTED BY ("The Quartermaster" by default), TIMESTAMPS.

### Identity
- **Wiki SSO (`/login`)** — classic MediaWiki `action=login` against
  noisebridge.net/api.php. Username + password forwarded once,
  discarded. Same pattern as nbarchive.
- **Logout (`POST /logout`)** — drops session.
- **View-as-user toggle (`POST /me/view-as`)** — admin can flip into
  pretend-mode to preview the public UI; AS USER ↔ AS ADMIN button in
  the title bar.

### Characters
- **Listing (`/me/characters`)** — card grid, active state highlighted
  green, ☠ skull retire icon bottom-right, MAKE ACTIVE button.
- **Create (`/me/characters/new`)** — form with name, class, optional
  primary guild. Welcome grant fires on creation (100 XP default).
- **Activate / delete** — form-driven, owner-scoped, idempotent. Active
  reassigns to oldest remaining on delete.

### Claim / release
- `POST /quests/{id}/claim` and `POST /quests/{id}/release` use the
  user's active character. State machine:
  open → (claim count ≥ party_min) → claimed → (release ↓ party_min) →
  open. Validates terminal status, party_max, double-claim.

### Admin
- `/admin/` dashboard — user count, quests by status, deleted count, seed
  pool stats (per-channel, top skills), recent users + quests.
- `/admin/quests` — every quest, filterable, with EDIT links per row and
  a deleted-row strikethrough toggle.
- `/admin/quests/{id}/edit` — form for contact_text, verifier_text,
  internal_notes.
- `/admin/users` — every non-system user.
- `/admin/templates` — the 348-entry seed pool, filter by channel + skill.
- Admin allow-list lives in `economy.yaml` under `admin.usernames`,
  case-insensitive, SIGHUP-reloadable.

### API surface (`/api/v1/`)
- `GET /healthz`, `/version`, `/economy`, `/stats`
- `GET /guilds`, `/locations`
- `GET /quests` (cursor-paginated), `GET /quests/{id}` (public-safe view)

### Schema (Postgres on zephyr)
- `users`, `characters`, `character_classes` (7 player classes — Bard,
  Bio-Tinkerer, Custodian, Hacker, Mechanic, Scribe, Sysadmin),
  `npc_quest_givers` (table exists, no rows yet)
- `guilds` (17 NB-flavored: facilities, woodshop, rack, treasurer,
  safety, electronics, sewing, spacebridge, writing, gaming,
  rubber-ducky, philosophy, 3d-printing, laser-cutter, ai-ml, secretary,
  metaguild)
- `locations` (22: 20 physical NB rooms + Discord + Meetup)
- `quests` (349 — 1 seed + 348 ingested), `quest_claims`, `quest_boosts`,
  `xp_transactions`, `api_keys`
- Active migrations: `0001..0005` (latest: `contact_text` /
  `verifier_text`)

---

## Stubbed / placeholder

- **Front-page activity feed** is a hand-coded mock list. Real SSE-driven
  feed comes with the simulator.
- **Active character's "current task" panel** always shows
  `RESTING / (no quest claimed)`. Will populate from active claim once the
  simulator runs claims to maturity.
- **Boost mechanic** is fully spec'd and the table exists, but no UI to
  spend XP on a boost yet.
- **Level-up** mechanic spec'd; no UI to spend XP on a level yet.
- **Posting fee** — plumbing exists but humans can't post quests through
  the UI yet, so nobody pays a fee in practice.
- **Verification step** — disabled (per demo decision); schema in place.

---

## Not built yet

- **Simulator** — the tick loop that advances `sim_state`, fires NPC
  posts and character auto-claims/auto-completes, writes to
  `simulation_events`, drives the SSE feed. The biggest remaining slice.
- **NPC quest-giver seeding** — schema is there; no rows. The simulator
  will populate.
- **Live SSE feed** at `/api/v1/feed/stream`.
- **Per-character public page** at `/c/{character_id}`.
- **Leaderboard page** at `/leaderboard`.
- **Wiki user-page badge** endpoints under
  `/api/v1/users/by-wiki/{username}/badge.{svg,json,html}` (for embedding
  on NB wiki user pages).
- **Admin reset endpoint** to wipe the simulation state on demand
  (preserves users, guilds, locations, NPC defs, seed pool).
- **Discord linking flow** — explicitly deferred; `users` carries the
  metadata columns but no `/link` slash-command flow.

---

## Data pipeline (one-shot, already run)

1. `scripts/mine_discord.py` walked
   `~/projects/git/noisebridge/nbdiscord/backups/Noisebridge_current/channels`
   and surfaced ~627 task-shaped Discord messages across 22 channels
   (help-wanted, facilities, fabrication-n-lasers, woodshop / woodshop-wall,
   electronics, safety-council, plus extended sweep through sewing,
   3d-printing, ai-ml, python, philosophy, games, spacebridge, writing,
   wiki-docs-wg, zine, donations, secretary-guild-private, etc.).
2. `scripts/curate_discord.py` ran them through the LiteLLM router
   (loki/qwen3-coder-30b primary; spartacus/styx 14B Qwens timed out
   often, so a top-up pass on loki only). Output: 348 entries with
   cleaned title, ≤200-char description, xp suggestion, urgency,
   quality score.
3. `scripts/tag_skills.py` assigned 1–3 skills from
   `data/skill_vocab.yaml` (32 slugs across 7 categories).
4. `scripts/ingest_pool.py` loaded the tagged YAML into the live
   `quests` table, all status='open', all `creator_*_id`=NULL so they
   render as "POSTED BY · The Quartermaster". Provenance trail
   (channel + msg id + author + date) lives in `internal_notes`,
   admin-visible only.

The pipeline is repeatable but not part of the runtime. We don't
generate quests with LLMs at runtime; that was a one-shot data-prep
step.

---

## Operational state

- **Service:** `questboard.service` on zephyr (Debian, Postgres 18,
  Python 3.13). Runs as user `nthmost` out of
  `~/projects/nthmost-systems/quest-board` against the synced repo.
  Listens on `127.0.0.1:8080`.
- **Reverse proxy:** zephyr's Apache vhost
  (`/etc/apache2/sites-available/nbquest.nthmost.net.conf`) proxies
  HTTPS at `nbquest.nthmost.net` to `127.0.0.1:8080` (local; no
  WireGuard hop).
- **TLS:** Let's Encrypt cert managed by certbot.
- **Secrets:** `~/projects/nthmost-systems/.secrets/questboard-db.env`
  and `questboard-session.env`, mode 600, synced to zephyr.
- **Backups:** not yet automated. Need to wire up `pg_dump` cron on
  zephyr.

### Enki — quiesced 2026-05-09

Demo originally lived on enki (Ubuntu 24.04, Postgres 16). On
2026-05-09 the demo was migrated off enki to zephyr so the demo
and the eventual real Noisebridge quest/task board (which will live
on enki) stop sharing a database and a hostname. Enki state:

- `questboard.service` stopped and disabled (unit file still present).
- `/home/nthmost/projects/nthmost-systems/quest-board` and the local
  Postgres `questboard` DB are intact, kept as a reference snapshot
  while the enki-side spec gets figured out.
- The future enki deployment is **not** a clone of the demo —
  expect a separate database, a separate hostname (likely
  `quests.noisebridge.net`), and likely a different schema/feature
  set once the NB community decides what they want.
