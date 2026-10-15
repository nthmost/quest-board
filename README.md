# Actropolis

A quest board for the Actropolis network of makerspaces — a Progress-Quest-style
task board built so a future "real" version can be inherited from the same
codebase without rewriting.

**Live:** <https://quests.actropolis.org/>

---

## What changed (Oct 2026)

Formerly the "Noisebridge Quest Board." Now rebranded **Actropolis** and generalized
to span multiple makerspaces:

- **Independent accounts.** Auth no longer proxies to the Noisebridge wiki. Accounts
  are local (username + Argon2id password), created via `/register`, changed via the
  profile panel (`/me/password`). Admin bootstrap/reset: `python -m scripts.set_password <user>`.
- **Spaces (makerspaces).** A `spaces` table models member sites (Noisebridge, Sequoia
  Fabrica, OpenCircuit SF, Sudo Room). Users pick a **primary makerspace** on their
  profile; quests can be scoped to a space (shown on cards + detail, filterable in browse).
- **Hosting.** Served at `quests.actropolis.org` (Apache reverse-proxy → uvicorn :8080 on
  zephyr). Admin allow-list lives at `/home/nthmost/.questboard-economy.yaml` (outside the
  repo, pointed to by an `ECONOMY_YAML_PATH` systemd drop-in).

> **⚠ Civic-hours caveat.** SPEC §1 / §4 and the DESIGN_NOTES civic-hours certificate
> depended on the fact that *wiki accounts were issued only after in-person admin
> verification* — making `wiki_username` ≈ a verified human. **Independent self-serve
> signup breaks that chain.** Before using Actropolis records for volunteer-hour /
> civic-credit certification, re-establish a personhood-verification step (e.g. admin
> approval of accounts, or per-space vouching). See SPEC.md §1.

---

## Two products, one codebase

This project carries two product visions side by side. The schema, code,
and architecture are designed to support both; only configuration and a
handful of toggles distinguish them.

| | **Demo (now)** | **Real (eventually)** |
|---|---|---|
| Audience | Anyone who wants to play | Noisebridge members |
| Characters | Up to 4 per account | 1 per account (config flag) |
| NPC posters | Yes (system voice = "The Quartermaster") | None — humans post real asks |
| Auto-play | Characters claim/complete on a sim clock | No — humans drive every action |
| Sim clock | 30× speedup, ~1 month per real day | Wall clock, no compression |
| Verification step | Off | Configurable per quest |
| URL | `quests.actropolis.org` | likely `quests.noisebridge.net` |

The demo is the immediate deliverable. The real productivity tool is
where this is headed once people see what the rhythm of a quest board
could feel like.

---

## Where to look for what

Read these in order:

1. **[STATUS.md](./STATUS.md)** — what's actually built and live right now,
   what's stubbed, what's next. Always reflects the head of `main`.
2. **[SPEC.md](./SPEC.md)** — the long-term productivity tool design.
   Defines the data model, economy mechanics, API surface, state machine.
   The demo is built on top of this spec.
3. **[DEMO.md](./DEMO.md)** — the Progress-Quest-style demo as a delta on
   SPEC.md. New entities (characters, NPCs, sim clock, simulation events),
   modifications, and what reverts when `demo.enabled = false`.
4. **[UI.md](./UI.md)** — visual register, palette, panel system,
   page-by-page reference, component vocabulary, anti-patterns observed.
5. **[DEPLOYMENT.md](./DEPLOYMENT.md)** — ops runbook for the live
   service: hosts, secrets, Apache vhost, systemd, backups.
6. **[ANSIBLE_future.md](./ANSIBLE_future.md)** — non-binding sketch of
   how this would scale to a multi-host fleet (Pis around the space).

---

## Local dev

```bash
# Postgres running locally (assumed)
createdb questboard

git clone https://github.com/nthmost/quest-board.git
cd quest-board
python3 -m venv .venv
.venv/bin/pip install -e ".[dev]"

export DATABASE_URL="postgresql+psycopg://localhost/questboard"
export ECONOMY_YAML_PATH="$(pwd)/economy.example.yaml"
export SESSION_SECRET="$(openssl rand -base64 48)"

.venv/bin/alembic upgrade head        # migrations 0001..0005
.venv/bin/python scripts/seed.py      # guilds, locations, 3 test users
.venv/bin/python scripts/ingest_pool.py   # ~348 NB-flavored quests
.venv/bin/uvicorn app.main:app --reload --port 8080
```

Then <http://localhost:8080/> for the front page,
<http://localhost:8080/api/v1/docs> for the OpenAPI explorer.

To poke as an admin locally, edit `economy.example.yaml` and add your username (case-insensitive) to `admin.usernames`, then
SIGHUP or restart.

---

## Repo layout

```
quest-board/
├── README.md                      # ← you are here
├── STATUS.md                      # current build state
├── SPEC.md                        # the "real" productivity tool
├── DEMO.md                        # Progress Quest demo, delta on SPEC
├── UI.md                          # visual reference
├── DEPLOYMENT.md                  # ops runbook
├── ANSIBLE_future.md              # multi-host future sketch
│
├── pyproject.toml                 # FastAPI + SQLAlchemy + Alembic + Jinja
├── alembic.ini
├── alembic/versions/0001..0009    # full migration chain
├── economy.example.yaml           # all economy knobs in one file
│
├── app/
│   ├── main.py                    # FastAPI factory, SIGHUP handler, asset_v
│   ├── config.py                  # YAML loader
│   ├── db.py                      # SQLAlchemy engine + session
│   ├── auth.py                    # local login/register, admin gate, view-as toggle
│   ├── local_auth.py              # Argon2id password hashing / validation
│   ├── models/                    # one file per table
│   ├── schemas/                   # Pydantic in/out
│   ├── services/                  # business logic (tiny, pure-ish)
│   ├── routes/                    # pages.py, me.py, admin.py, api routers
│   ├── templates/                 # Jinja
│   └── static/css/nes.css         # all styles
│
├── data/
│   ├── skill_vocab.yaml           # 32-slug controlled vocabulary
│   └── quest_templates/
│       ├── discord_mined.yaml     # raw mined Discord candidates (~600)
│       └── discord_tagged.yaml    # 348 LLM-curated + skill-tagged seeds
│
└── scripts/
    ├── seed.py                    # guilds, locations, sample users + quests
    ├── mine_discord.py            # walk archives, surface task-shaped messages
    ├── curate_discord.py          # LLM pass: is_task / clean title / xp
    ├── tag_skills.py              # LLM pass: pick 1-3 skills from vocab
    └── ingest_pool.py             # YAML → live quests table
```

---

## Coding conventions

Adapted from the standards in `~/projects/git/neon-nerdsnipe/CLAUDE.md`:

- **Tiny functions** (5–15 lines) doing one thing each. If it's getting
  long, factor.
- **All imports at module top.** No lazy in-function imports.
- **Minimal try/except.** Wrap only the line(s) that can fail; prefer
  early returns and guard clauses over nested error handling.
- **Type hints everywhere.** Pydantic for boundary types; SQLAlchemy 2.0
  `Mapped[...]` columns.
- **Flat over nested.** Three lines of repetition is better than a
  premature abstraction.
- **No emoji in code or comments** unless asked. The retro UI accent
  glyphs (♣ ♦ ★ ⌬ ▲ ☠) are the exception — they're part of the
  intentional visual register.

`ruff check app/ scripts/ alembic/versions/` runs clean. `B008` is
ignored (Depends-in-defaults is the canonical FastAPI pattern).

---

## Important context for new sessions

**Architecture commitments locked in:**

- Character is the primary actor in *both* modes. Quests, claims, boosts,
  and the XP ledger all attach to `character_id`. Users are pure wiki
  identity. The real version constrains 1:1 via config; the demo allows
  up to 4 characters per user.
- `quartermaster` is reserved as the system voice (default attribution
  on quests with no concrete poster). Players can't pick it as a class.
- `internal_notes` is admin-only; everything else is public-safe by
  default with authed reads getting more.
- Verification is disabled for the demo; schema column stays so the
  real version can re-enable it per quest.

**Recent decisions worth not relitigating:**

- Wiki SSO is classic MediaWiki `action=login`, not OAuth (the NB wiki
  has no OAuth extension installed). Same pattern as nbarchive.
- Quest pool was mined from NB Discord archives (`#help-wanted`,
  `#facilities`, `#fabrication-n-lasers`, etc.), curated through the
  LiteLLM router, and skill-tagged against `data/skill_vocab.yaml`. We
  don't run LLM gen at runtime — that was a one-shot data-prep step.
- All economy values live in `economy.example.yaml` (deployed copy at
  `/etc/questboard/economy.yaml` on enki). SIGHUP reloads.

**Where the live service runs:** enki (NB), behind zephyr's Apache
which proxies over WireGuard. uvicorn on `0.0.0.0:8080`. systemd unit
`questboard.service`. See DEPLOYMENT.md.

---

## What this is *not*

- Not a real productivity ledger yet. Nothing here governs Noisebridge
  resources or member status.
- Not a Discord bot. We mined the archive for seed data; we don't post
  back, listen, or relay.
- Not a public commitment to ship. The demo is a vibes-check; the real
  version may or may not happen depending on community traction.
