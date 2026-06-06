# Quest Board — Progress Quest Demo

> **Orientation:** This document is the **delta on top of [SPEC.md](./SPEC.md)**
> describing the Progress-Quest-style demo at <https://nbprogressquest.nthmost.net/>.
> SPEC.md is the long-term Noisebridge productivity-tool design; this is what
> we're actually shipping first. For what's currently built, see
> [STATUS.md](./STATUS.md). For visual reference, see [UI.md](./UI.md).
> If you're brand new, start with [README.md](./README.md).


**Status:** Design draft, 2026-05-08
**Hostname:** `nbprogressquest.nthmost.net` (the production deployment lives at `nbquests.nthmost.net`)
**Purpose:** Demonstrate the quest-board concept by simulating a month of Noisebridge guild activity in a single real-world day, in the style of Progress Quest. Visitors log in via the wiki, create up to 4 characters, and watch them auto-play.

This document is a delta on top of [SPEC.md](./SPEC.md). Rules in SPEC.md still apply unless explicitly changed here.

---

## 1. What the demo is

A passive idle game. Player logs in via wiki SSO, creates a character (name + class + primary guild), and watches the character claim and complete quests automatically. The activity feed scrolls flavor text in the manner of Progress Quest. After enough sim time the character levels up. Players can create up to 4 characters per wiki account, and delete any of them.

NPC quest-givers seed the world with quests. Quests are sourced from real Noisebridge Discord channels (#fabrication, #help-wanted, project-forum posts) and supplemented with LLM-generated weirdness for color. Real human posters and claimers are still possible but not required — the world keeps moving on its own.

The "real" implementation is the productivity tool described in SPEC.md. The demo is a stepping stone that happens to share most of its data model.

---

## 2. Demo ↔ Real differences

| Concern | Demo | Real (post-demo) |
|---|---|---|
| Character ↔ User | 1:N (max 4) | 1:1 (DB constraint) |
| Character can be deleted | yes, freely | only by admin |
| NPC quest-givers | yes, primary source | none, all quests human-posted |
| Auto-play | yes, characters claim/complete on their own | no, humans drive everything |
| Sim clock | tick-based, 30× speedup | wall-clock; one second is one second |
| Posting fee | always charged per YAML; NPCs exempt | always charged per YAML |
| Welcome grant | fires on **character** creation | fires on **character** creation (which == user creation under 1:1) |
| Verification step | **disabled** — quests go open → claimed → done | configurable per quest |
| LLM generation | none at runtime; used only for offline data prep | none at runtime |
| World reset | admin button | not applicable |

**Character is the primary actor in both modes.** Quests, claims, boosts, and the XP ledger all attach to character_id. Users are pure identity (wiki_username + discord linking metadata). The real version simply enforces unique(user_id) on `characters`; everything else is the same.

The schema accommodates both modes; demo-only behavior (NPCs, auto-play, sim clock, multi-character) is gated by an `economy.yaml` flag (`demo.enabled`).

---

## 3. New & modified data model

### `characters` (new)
| column | type | notes |
|---|---|---|
| id | bigserial PK | |
| user_id | bigint FK users(id) not null | demo: 1..4 per user; real: unique |
| name | text not null | display name; uniqueness scoped to user only |
| class_slug | text FK character_classes(slug) | `hacker`, `mechanic`, `bard`, etc. |
| primary_guild_id | int FK guilds(id) nullable | character's chosen guild |
| xp_balance | int not null default 0 | CHECK ≥ 0; **moves here from `users`** for the demo |
| level | int not null default 1 | |
| created_at | timestamptz | |
| deleted_at | timestamptz nullable | soft-delete; XP transactions remain |
| flavor_seed | int not null | RNG seed for personalized flavor text |

Application-level CHECK: `count(active characters where user_id = X) <= demo.max_characters_per_user` (default 4).

### `character_classes` (new, seeded)
| column | type | notes |
|---|---|---|
| slug | text PK | |
| name | text | display name |
| description | text | one-line lore |
| guild_affinity | jsonb | `{"facilities": 0.4, "bobs-hardware": 0.3, ...}` |
| flavor_kit_slug | text | reference to a flavor template kit |

### `npc_quest_givers` (new, seeded)
| column | type | notes |
|---|---|---|
| id | serial PK | |
| handle | text unique | `the-quartermaster`, `bobs-ghost`, etc. |
| display_name | text | |
| guild_id | int FK guilds(id) nullable | which guild they post for |
| post_cadence_sec | int not null | sim seconds between posts; jittered ±20% |
| description | text | persona blurb |
| created_at | timestamptz | |

NPCs are *not* `users` rows — they're separate. Quests posted by NPCs set `creator_user_id = NULL` and `creator_attribution = 'npc:<handle>'`.

### `quest_templates` (new)
Templates feed the slot-filling generator. Hand-curated, mined from Discord, or LLM-extrapolated.

| column | type | notes |
|---|---|---|
| id | bigserial PK | |
| source | text | `discord:<channel>` \| `template:<slug>` \| `llm` |
| guild_slug | text nullable | suggested guild |
| location_slug | text nullable | suggested location |
| title_template | text | with `{{slot}}` placeholders |
| description_template | text | with `{{slot}}` placeholders |
| skills | text[] | suggested skill tags |
| xp_range | int4range | `[5, 50)` etc. |
| created_at | timestamptz | |

Slot dictionaries (`thing`, `material`, `tool`, `mishap`) live in YAML alongside the templates.

### `simulation_events` (new, append-only)
Activity feed durable log. SSE replays from here on reconnect.

| column | type | notes |
|---|---|---|
| id | bigserial PK | |
| sim_time | timestamptz not null | the sim_now when this happened |
| real_time | timestamptz not null | wall-clock when fired |
| character_id | bigint FK characters(id) nullable | actor, when applicable |
| quest_id | bigint FK quests(id) nullable | quest involved, when applicable |
| event_type | text | `quest_claimed`, `quest_completed`, `level_up`, `quest_posted`, ... |
| payload | jsonb | event-specific extras (flavor text rendered, deltas, etc.) |

Indexed `(sim_time desc)` and `(character_id, sim_time desc)`.

### `sim_state` (new, single-row)
The simulator's metadata.

| column | type | notes |
|---|---|---|
| id | int PK CHECK = 1 | enforce single row |
| sim_epoch | timestamptz | sim_now at the demo's start |
| real_epoch | timestamptz | wall-clock at the demo's start |
| speedup | int not null default 30 | sim seconds per real second |
| paused | bool not null default false | |
| last_tick_real | timestamptz nullable | wall-clock of most recent tick |
| last_tick_sim | timestamptz nullable | sim_now of most recent tick |

`sim_now()` = `sim_epoch + (now() - real_epoch) * speedup`.

### Modifications to existing tables

- `xp_transactions` gets a `character_id bigint FK characters(id) nullable` column. In demo mode, all character-derived transactions populate this; `user_id` mirrors the character's owner. In real mode, this column stays null.
- `quest_claims.user_id` becomes `claimer_id`, generic over (user, character). In demo, claims are by characters. Implementation: add `character_id`, leave `user_id` nullable, enforce that exactly one is non-null per row.
- `quests.xp_source` gains values: `npc_template`, `npc_llm`, `discord_mined`.
- `users` keeps `xp_balance` and `level` columns but they're inert in demo mode (everything happens at character level).

---

## 4. Character classes

Initial seed list (refine before launch).

**`quartermaster` is reserved for the system** — it's the default
attribution shown on quests with no concrete poster (e.g.,
admin-seeded test quests, system-generated chores). Players can't
pick it; NPC quest-givers can be modeled separately.

| slug | name | flavor |
|---|---|---|
| `hacker` | Hacker | "Will compile from source on principle." |
| `mechanic` | Mechanic | "Has Loctite in their backpack." |
| `bard` | Bard | "Owns a soldering iron mostly because it's pretty." |
| `sysadmin` | Sysadmin | "Speaks in incident-report tense." |
| `bio-tinkerer` | Bio-Tinkerer | "Asks questions about the autoclave." |
| `custodian` | Custodian | "Has Strong Opinions about the dish rack." |
| `scribe` | Scribe | "Won't let a wiki page rot on their watch." |

Each class has a `guild_affinity` map biasing which quests it drifts toward, and a `flavor_kit` shaping its action verbs (`compiles`, `welds`, `tunes`, `triages`, ...) and idle text (`pauses to refactor a comment`, `scrutinizes a label maker tape`).

---

## 5. Quest generation pipeline

### Source 1 — Discord-mined templates
Offline ingest pass walks the archives at `~/projects/git/noisebridge/nbdiscord/channel_exports/` (and any `backups/discord/...` dumps) for messages in:

- `#fabrication`
- `#help-wanted`
- `#projects-cms`, project forum posts
- `#bobs-hardware`, `#woodshop-wall`, `#sewing`, `#3d-printing`, `#electronics`, `#hydroponics`, `#ceramics`, `#robotics`, ... (any topic channel that historically hosts requests)

A small extractor (LLM-assisted, qwen2.5:7b) pulls request-shaped messages, normalizes them into `quest_templates` rows with `source = 'discord:<channel>'`. Output reviewed manually before going into the live pool. Done once during demo prep, occasional refresh.

### Source 2 — ~~LLM extrapolation~~ *(dropped)*
Originally planned: NPCs ask Ollama at runtime to generate fresh quests. **Cut from scope** 2026-05-09 — the demo will draw exclusively from the seed pool (Discord-mined + hand-curated). The LLM was used once during data prep to filter and clean the mined messages; we don't persist its scoring as live state and we don't generate new quests at runtime.

### Source 3 — Hand-curated templates
Small set of explicitly authored templates with rich slot dictionaries for the absurdist Progress Quest tone ("Fish a {{tool}} out of the {{location}} sink trap"). Lives in `data/quest_templates/*.yaml` in the repo. Reviewed and version-controlled.

### NPC posting loop
Every NPC has a `post_cadence_sec`. The simulator schedules each NPC's next post at `sim_now + (cadence * jitter)`. When their turn fires:
1. Pick a quest from the seed pool (Discord-mined + hand-curated templates), filtered to the NPC's guild.
2. Materialize it: copy fields into the live `quests` table, fire a `quest_posted` simulation event, schedule the next post.

---

## 6. Simulation architecture

### Sim clock
`sim_now()` reads from `sim_state` and returns `sim_epoch + (now() - real_epoch) * speedup`. With `speedup = 30`, 1 real second = 30 sim seconds, so 1 real day ≈ 1 sim month.

### Tick loop
A single async task runs in the FastAPI lifespan:

```python
async def tick_loop(app):
    while not app.state.shutdown:
        await simulator.tick(sim_now())
        await asyncio.sleep(1)  # 1 real second
```

`simulator.tick(now)` fires anything scheduled for `<= now`:

1. **NPC posts** due — generate and insert quests.
2. **Character actions** due — see below.
3. **Quest completions** — characters with active claims whose claim matures (sim duration elapsed) move to `done`, run payout per the SPEC.md ledger rules, fire `quest_completed` event.
4. **Level-ups** — after each character's xp_balance changes, check curve thresholds and auto-spend if `auto_level_up = true` (configurable; default yes for demo).

Tick handler is idempotent: re-running a missed tick yields the same world state.

### Character auto-play
For each living character on each tick:

1. If character has an active claim, do nothing (mature on its own schedule).
2. Else, with probability `p_claim_per_tick` (configurable), pick a quest:
   - Filter to open quests in guilds matching `class.guild_affinity` (weighted random).
   - Skip quests where `party_max` is full.
   - Insert a `quest_claims` row with `character_id`.
   - Schedule completion at `sim_now + duration` where duration is sampled from the quest's xp range × class speed coefficient.
   - Fire `quest_claimed` event with rendered flavor text.
3. With small probability, generate an idle event ("Bee tunes a synthesizer pedal that wasn't out of tune").

### Event scheduling
Two scheduled-event mechanisms:
- **NPC post schedule** in the NPC row (`next_post_at sim_time` column).
- **Active claim maturation** in the `quest_claims` row (`mature_at sim_time` column — added for demo).

Tick handler queries each independently; no single global priority queue needed.

---

## 7. SSE activity feed

`GET /api/v1/feed/stream` (public read) serves a Server-Sent Events stream of `simulation_events` newest-first. On connect, replays the last N events; thereafter pushes events as the tick handler appends them. In-process pub/sub via an `asyncio.Queue` per connected client; the tick handler broadcasts after each event insert.

`GET /api/v1/feed?since=<event_id>&limit=N` exposes the same data via plain HTTP for clients that can't use SSE.

Event payloads include rendered flavor text so the client doesn't need template knowledge. The tick handler picks templates from the actor's `flavor_kit` at event-creation time.

---

## 8. New API endpoints (demo-specific)

```
# Characters
GET    /api/v1/me/characters          # list current user's characters
POST   /api/v1/me/characters          # create (name, class_slug, primary_guild_slug)
DELETE /api/v1/me/characters/{id}     # soft-delete (free a slot)
GET    /api/v1/characters/{id}        # public summary (name, class, level, xp, recent activity)

# Classes & NPCs (public)
GET    /api/v1/classes
GET    /api/v1/npcs

# Activity feed
GET    /api/v1/feed                   # paginated history
GET    /api/v1/feed/stream            # SSE stream

# Sim controls (admin)
POST   /api/v1/admin/sim/pause
POST   /api/v1/admin/sim/resume
POST   /api/v1/admin/sim/reset        # rewind sim_epoch and clear ephemeral state

# Auth
GET    /api/v1/auth/wiki/login
GET    /api/v1/auth/wiki/callback
POST   /api/v1/auth/logout
```

The existing read endpoints (`/quests`, `/guilds`, `/locations`, `/stats`, `/economy`) keep working unchanged.

---

## 9. Frontend

**Stack:** server-rendered Jinja + htmx + SSE, served from the same FastAPI process under `/`. Static assets under `/static`.

**Pages:**
- `/` — public landing. Activity feed (live SSE). "Log in via wiki" CTA. Maybe top-N leaderboard.
- `/me` — your characters (cards), with create/delete buttons.
- `/me/characters/new` — character creation: name, class picker, guild picker.
- `/c/{character_id}` — character sheet: stats, current quest, recent events. Public.
- `/leaderboard` — top characters by xp/level.
- `/quests` — current open and recent quests, scrollable.

**Aesthetic — *to be designed together***. Strong starting points from `dumps.nthmost.net`:

- Press Start 2P pixel font
- NES palette (`#0c0c0c` bg, `#88401c` brown borders, `#fcd058` yellow highlights, `#c82020` red, `#fcfcfc` white text, `#6888fc` blue accents)
- Thick (`4px solid`) NES-style dialogue borders
- `image-rendering: pixelated` for any bitmap art
- Scene art with overlay layers (animated GIFs for ambient motion)

Open aesthetic decisions (we'll do a pass together):
- Character sheet layout (Progress Quest is dense vertical lists; we could do a horizontal NES-RPG layout instead)
- Whether to commission/generate per-class portraits
- Ambient scene behind the main UI — cave? hackerspace floor at night? rotating per character location?
- Sound effects — yes/no/optional toggle
- Animated pixel fire / smoke layers (the dumps page already has a working pattern)

---

## 10. Configuration extensions

```yaml
# Added to economy.yaml
demo:
  enabled: true
  max_characters_per_user: 4
  speedup: 30                    # sim_seconds per real_second
  tick_interval_sec: 1
  feed_replay_size: 50           # events served on SSE reconnect
  auto_level_up: true

  npc:
    post_source_weights:
      template: 0.6
      discord_mined: 0.3
      llm: 0.1
    default_post_cadence_sec: 1800  # sim seconds; per-NPC overrides

  character:
    p_claim_per_tick: 0.05       # probability a free character starts a claim each sim tick
    welcome_grant_amount: 100    # XP credited on character creation
    flavor_text_idle_chance: 0.02

  reset:
    schedule: "weekly_monday_00:00_UTC"
    preserve_class_seeds: true
```

---

## 11. Out of scope for the demo

- Multi-user collaboration on the same character
- Real-money or real-trust mechanics
- Permanent leaderboards across resets (each reset starts fresh)
- Discord posting back to Discord ("our character did X!")
- Mobile-first UX (desktop pixel-art layout is the pitch)
- Actual quest verification — characters self-report completion, NPCs don't dispute

---

## 12. Open questions

1. **Discord ingest scope.** Mining the existing local archives is cheap; pulling live from the Discord API is more work. Recommend **archive-only for v1 demo**; live ingest is a separate feature.
2. **Class portraits.** Generate via image model or hand-pixel? Punt until aesthetic pass.
3. **Reset cadence.** Weekly seems right for "a fresh world to log into" but might be too frequent if people want to grow attachment to a character. Could be admin-on-demand instead.
4. **NPC count.** Start with 4–6 distinct NPC personas, one per major guild theme. Scale up if it feels sparse.
5. **Wiki OAuth scopes.** `basic` (just username) is enough; confirm at consumer registration time.
6. **Public access without login.** Should anonymous visitors see the activity feed and character sheets, or just a "log in to see the world" splash? Recommend **public read** to make sharing the demo easy.
