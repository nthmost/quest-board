# Noisebridge Quest Board — API Spec (v1 draft)

> **Orientation:** This document is the long-term productivity-tool design.
> The Progress-Quest-style demo currently being built is a delta on top of
> this spec — see [DEMO.md](./DEMO.md). For what's actually built right now,
> see [STATUS.md](./STATUS.md). For visual reference, see [UI.md](./UI.md).
> If you're brand new, start with [README.md](./README.md).


**Status:** Draft, 2026-05-19 (adds donor bounties + claim reporting; see [DESIGN_NOTES_2026-05-19_donor_bounties_and_claim_reporting.md](./DESIGN_NOTES_2026-05-19_donor_bounties_and_claim_reporting.md) for rationale)
**Host:** enki (NB), Ubuntu 24.04, 31 GB RAM, i5-14450HX, CPU-only Ollama
**Stack:** FastAPI + SQLAlchemy + Alembic, PostgreSQL, local Ollama (qwen2.5:7b + llama3.2:3b)
**Public hostname (interim):** `nbquests.nthmost.net` (advocate for `quests.noisebridge.net` later)

---

## 1. Design principles

- **Character is the primary actor.** Quests are claimed, completed, and boosted by characters, not users. The XP ledger writes to character_id. Users are pure identity (wiki_username + Discord linking metadata, no economy fields). The real version constrains each user to exactly one character; the demo allows up to 4. Same code path either way.
- **One core entity: `Quest`.** Sub-quests, tasks, errands are all just quests with a `parent_quest_id`. Maximum depth is YAML-configurable (`quests.max_depth`, default 2) with an absolute ceiling of 3. Depth-3 supports "maxi-quests" — e.g. a *Journeyman in Guild X* container holds quests, which themselves hold tasks.
- **XP is a real economy.** Quests mint XP on completion; users can spend XP on (a) **levels** (vanity sink) and (b) **boosting** quests they want done. Inflation is tolerated — this is a social-credit system, not a closed currency.
- **Donor bounties are real dollars, gifted to NB.** A donor pledges $X conditional on a quest being completed; on terminal payout, NB collects the gift. The bounty never flows to the doer (no wage, no contractor pay, no escrow). Volunteers remain volunteers; donors get a 501(c)(3) acknowledgment. The mechanic is a *conditional restricted gift*, not a market price.
- **Time-and-notes reporting at claim is measurement, not competition.** Per-claimer self-reported minutes, done-state, free-text notes, and an optional photo are captured at claim completion. The data exists to be aggregated (operational-cost transparency, calibrated bounty pricing, grant-writing volunteer-hour totals). No speedrun bonuses, no minimum-time thresholds, no XP modifier tied to duration.
- **Verification is social by default.** Public submissions (notes + photo + time + party) create the audit trail; software does not adjudicate "done" for most tasks. The `requires_verification` flag is reserved for genuinely high-stakes work.
- **Wiki identity is in-person verified.** Noisebridge wiki accounts are issued only after an admin sits with the prospective member in person and verifies them. This single fact is **load-bearing** for the civic-hours certificate (§4): the personhood-to-account binding is established once at admin-mediated signup and inherited by every claim downstream. If wiki-account policy ever loosens to self-serve signup, the civic-hours story breaks and the certificate text must be updated. This dependency is documented here on purpose.
- **Discord integration is deferred.** `users` table carries `discord_user_id` / `discord_username` columns so the data is captured opportunistically; no flows in v1.
- **Public-read by default.** GETs return non-sensitive fields without auth so the BBS, Home Assistant @ NB, and ad-hoc scripts can consume freely.
- **Wiki is canonical identity** via MediaWiki OAuth.
- **LLM assist is opt-in and preview-only** via `/quests/draft`.
- **Economy rules live in YAML, not the database.** A single `economy.yaml` config file is the source of truth for tunable values; the API hot-reloads on SIGHUP. No "settings UI," no `system_config` table.

---

## 2. Data model

### `users`
Sourced from MediaWiki OAuth on first login.

| column | type | notes |
|---|---|---|
| id | bigserial PK | |
| wiki_username | text unique not null | from OAuth |
| wiki_user_id | bigint unique | MediaWiki internal id |
| discord_user_id | text unique nullable | metadata only in v1 |
| discord_username | text nullable | metadata only |
| xp_balance | int not null default 0 | denormalized cache; ledger is canonical. CHECK ≥ 0 |
| level | int not null default 1 | starts at 1; advances via explicit level-up spends |
| is_system | bool not null default false | true for the singleton treasury user; excluded from leaderboards / public listings |
| created_at | timestamptz | |
| last_seen_at | timestamptz | |

A single seeded `is_system = true` user (`wiki_username = '__treasury__'`, no `wiki_user_id`) owns the treasury balance when posting fees are routed to it. All public-listing endpoints filter `is_system = false`.

`xp_balance` is recomputed on every `xp_transactions` insert in the same DB transaction.

### `guilds` / `locations` (enumerated, admin-curated)
Same as before — see prior version. (Slugs, names, kind, etc.)

### `quests`

| column | type | notes |
|---|---|---|
| id | bigserial PK | |
| parent_quest_id | bigint FK quests(id) nullable | self-referential; depth enforced at app level per `quests.max_depth` |
| depth | int not null default 0 | 0 = root, 1 = child, 2 = grandchild. Computed at insert time from parent. Stored to avoid recursive CTE on every read. |
| rollup_mode | text | `manual` (default) \| `auto` |
| creator_user_id | bigint FK users(id) nullable | nullable for service-principal posts |
| creator_attribution | text nullable | free-form when no user FK |
| guild_id / location_id | FK | nullable |
| title | text not null | |
| description | text not null | required |
| skills | text[] | free-form |
| xp | int not null default 0 | base reward per claimer |
| xp_source | text not null default 'manual' | `manual` \| `llm_suggested` \| `template` |
| creator_bonus_xp | int not null | snapshot from YAML at creation |
| verifier_bonus_xp | int not null default 0 | snapshot from YAML at creation |
| posting_fee_charged | int not null default 0 | actual fee debited from creator at creation; 0 if exempt or fee disabled |
| posting_fee_destination | text nullable | `burn` \| `treasury` \| null (when fee=0) — frozen from YAML at creation |
| urgency | text | `low` \| `normal` \| `high` |
| due_date | timestamptz nullable | |
| party_min / party_max | int / int nullable | |
| requires_verification | bool default false | |
| verifier_user_ids | bigint[] | empty = creator only |
| status | text not null default 'open' | `open` \| `claimed` \| `done` \| `verified` |
| paid_out_at | timestamptz nullable | when XP minted; locks the quest |
| deleted_at | timestamptz nullable | soft-delete |
| created_at / updated_at / done_at / verified_at | timestamptz | |
| internal_notes | text nullable | sensitive |
| total_bounty_cents | int not null default 0 | denormalized sum of `quest_bounties.amount_cents` where `withdrawn_at IS NULL`; for sort/filter |
| bounty_count | int not null default 0 | denormalized count of active pledges |

CHECK: `paid_out_at IS NOT NULL` only when `status IN ('done','verified')`.

### `quest_claims`
One row per (quest, user) claim. The row is created on `POST /quests/{id}/claim` and stays even after release. Completion-reporting fields are populated at `POST /quests/{id}/done`.

| column | type | notes |
|---|---|---|
| quest_id, user_id, claimed_at | composite PK | |
| released_at | timestamptz nullable | unclaim sets this; row stays |
| time_spent_minutes | int nullable CHECK ≥ 0 | self-reported per person at completion; null until claim completes |
| done_state | text nullable | `full` \| `partial` \| `blocked`; null until claim completes |
| claim_notes | text nullable | public, free-form; encouraged at completion |
| reported_at | timestamptz nullable | when the completion-reporting fields were filled |

### `quest_bounties`
Per-donor pledges of real dollars conditional on quest completion. Charged on terminal payout.

| column | type | notes |
|---|---|---|
| id | bigserial PK | |
| quest_id | bigint FK quests(id) not null | |
| donor_user_id | bigint FK users(id) nullable | nullable for fully anonymous |
| donor_display_name | text nullable | for anonymous-but-credited donors; UI shows this instead of wiki_username |
| amount_cents | int not null CHECK > 0 | dollar pledge in cents |
| memo | text nullable | donor's dedication / reason |
| pledged_at | timestamptz not null default now() | |
| expires_at | timestamptz nullable | optional sunset; null = no expiry |
| collected_at | timestamptz nullable | set when NB captures payment (terminal-payout transition) |
| withdrawn_at | timestamptz nullable | donor cancelled or pledge expired uncollected |
| stripe_payment_method_id | text nullable | for charge-on-completion |
| stripe_payment_intent_id | text nullable | populated on collection |
| created_at | timestamptz default now() | |

A pledge is **active** when `collected_at IS NULL AND withdrawn_at IS NULL`. CHECK: at most one of `collected_at` / `withdrawn_at` may be non-null.

Indexes: `(quest_id) WHERE collected_at IS NULL AND withdrawn_at IS NULL`, `(donor_user_id, pledged_at desc)`.

### `quest_attachments`
Generic media table; v1 uses it for claim-completion photos but designed so quest-level attachments (reference images, before-shots) drop in later.

| column | type | notes |
|---|---|---|
| id | bigserial PK | |
| scope | text not null | `quest` \| `claim` |
| quest_id | bigint FK quests(id) not null | |
| claim_user_id | bigint FK users(id) nullable | non-null when `scope = 'claim'` |
| uploaded_by_user_id | bigint FK users(id) not null | |
| url | text not null | local path or object-storage URL |
| mime_type | text nullable | |
| caption | text nullable | |
| uploaded_at | timestamptz default now() | |

v1 storage: local filesystem under `/var/lib/questboard/attachments/`. The table makes migration to object storage transparent.

### `quest_boosts`
Tracks per-user XP contributions to a quest's payout pool.

| column | type | notes |
|---|---|---|
| id | bigserial PK | |
| quest_id | bigint FK quests(id) not null | |
| booster_user_id | bigint FK users(id) not null | |
| amount | int not null CHECK > 0 | XP spent at boost time |
| is_self_boost | bool not null | true when booster_user_id = quest.creator_user_id |
| spend_txn_id | bigint FK xp_transactions(id) not null | the negative ledger row |
| refund_txn_id | bigint FK xp_transactions(id) nullable | non-null if refunded on delete |
| refunded_at | timestamptz nullable | |
| created_at | timestamptz | |

Index: `(quest_id) where refunded_at IS NULL`.

### `xp_transactions`
The ledger. Every change to any user's `xp_balance` corresponds to exactly one row.

| column | type | notes |
|---|---|---|
| id | bigserial PK | |
| user_id | bigint FK users(id) not null | |
| amount | int not null | **may be negative for spends** |
| reason | text not null | enum below |
| quest_id | bigint FK quests(id) nullable | |
| boost_id | bigint FK quest_boosts(id) nullable | |
| memo | text nullable | |
| created_at | timestamptz default now() | |
| created_by_user_id | bigint FK users(id) nullable | non-null only for admin grants/corrections |

**Reason enum:**
| reason | sign | source |
|---|---|---|
| `welcome_grant` | + | system, on first user creation (one-shot per user) |
| `quest_completion` | + | system, on terminal transition |
| `quest_creation_bonus` | + | system, on terminal transition |
| `verifier_bonus` | + | system, on `verified` transition |
| `quest_posting_fee` | − | user (creator), on `POST /quests` |
| `quest_posting_fee_treasury` | + | system (treasury user), only when `destination = treasury` |
| `quest_posting_fee_refund` | + | system, on quest soft-delete (conditional, see YAML) |
| `quest_boost_spend` | − | user, on `POST /quests/{id}/boost` |
| `quest_boost_refund` | + | system, on quest soft-delete (conditional) |
| `level_up_spend` | − | user, on `POST /me/level-up` |
| `admin_grant` | + | admin (founding grants, etc.) |
| `admin_correction` | ± | admin (audit-trail correction) |

**Burn vs. treasury asymmetry:** when a posting fee is burned, only the negative `quest_posting_fee` row is inserted — the system XP supply decreases. When routed to treasury, both rows are inserted — total XP across the ledger is conserved. Querying `SUM(amount) GROUP BY reason` reveals the burn deficit and treasury inflow separately.

Indexes: `(user_id, created_at desc)`, `(quest_id)`, `(boost_id)`.

### `api_keys`
Same as before — `name`, `key_hash` (argon2), `scopes[]`, `revoked_at`.

---

## 3. Economy YAML

**Location:** `/etc/questboard/economy.yaml`. Loaded at startup; SIGHUP reloads.

```yaml
xp:
  creator_bonus_xp: 5            # frozen onto each quest at creation
  verifier_bonus_xp: 0           # frozen onto each quest at creation; 0 = unpaid duty
  boost_distribution: equal_among_claimers   # only mode supported in v1
  self_boost_policy: allowed_flagged          # allowed | allowed_flagged | disallowed
  boost_refund_on_delete: deleter_neq_booster # always | never | deleter_neq_booster

  posting_fee:
    enabled: true
    shape: flat                  # flat | proportional | floor_or_proportional
    flat_amount: 3               # used when shape ∈ {flat, floor_or_proportional}
    proportional_rate: 0.10      # used when shape ∈ {proportional, floor_or_proportional}
    floor_min: 1                 # only used when shape == floor_or_proportional
    destination: burn            # burn | treasury
    refund_on_delete: never      # never | if_unclaimed | always
    service_principal_exempt: true  # API-key posters skip the fee in v1

  llm_xp_suggestion:
    enabled: true
    threshold_quests: 20
    few_shot_sample_size: 10

  welcome_grant:
    enabled: true                # strongly recommended when posting_fee.enabled = true
    amount: 100                  # XP credited to every new user on first login
    memo: "welcome to Noisebridge Quests"

levels:
  curve: dnd5e                   # flat | linear | exponential | dnd5e | custom
  flat:        { cost: 50 }
  linear:      { base: 10 }      # cost(N→N+1) = base * N
  exponential: { base: 10 }      # cost(N→N+1) = base * 2^(N-1)
  dnd5e:       { scale: 0.01 }   # cost(N→N+1) = dnd5e_table_diff[N] * scale
  custom:      { costs: [] }     # explicit list; level cap = len(costs)+1
  max_level: 20

quests:
  max_depth: 2                   # 0..3. 0 = no children allowed. Hard ceiling: 3.

reopen_policy: disallow          # disallow | clone_only (functionally same) | admin_only

leaderboard:
  show_balances_publicly: true
  decay: none                    # none reserved for v1; future: half_life_90d, etc.
```

### Curve definitions (cost from level N → N+1)

| curve | formula |
|---|---|
| `flat` | `flat.cost` |
| `linear` | `linear.base * N` |
| `exponential` | `exponential.base * 2^(N-1)` |
| `dnd5e` | `dnd5e_table[N+1] - dnd5e_table[N]` then `* dnd5e.scale`, rounded |
| `custom` | `custom.costs[N-1]` |

Canonical D&D 5e cumulative XP table (used by `dnd5e` curve, multiplied by `scale`):
`[0, 300, 900, 2700, 6500, 14000, 23000, 34000, 48000, 64000, 85000, 100000, 120000, 140000, 165000, 195000, 225000, 265000, 305000, 355000]`.

With `scale: 0.01`, level 1→2 costs 3 XP, level 19→20 costs 500 XP. Tune per economy size.

---

## 4. Economy mechanics

### Quest depth enforcement
On `POST /quests` with `parent_quest_id IS NOT NULL`:

1. Look up parent's `depth`.
2. Compute `new_depth = parent.depth + 1`.
3. If `new_depth > quests.max_depth` (from YAML), reject with **409 Conflict**, body explains current limit.
4. If `quests.max_depth > 3` in config, the API refuses to start (hard ceiling).
5. Set the new quest's `depth = new_depth` and insert.

Re-parenting via `PATCH /quests/{id}` is allowed only if (a) the quest has no children, or (b) the resulting subtree fits under `max_depth` from the new parent. The simplest way to validate (b) is to recompute every descendant's prospective depth; reject if any exceeds.

Lowering `max_depth` in YAML does **not** retroactively prune existing quests. Quests that already exceed the new limit remain readable and completable, but you cannot create new children under them or re-parent them deeper. The startup check surfaces this on `GET /stats` (`economy_warnings: ["max_depth lowered; N quests exceed current limit"]`).

### Welcome grant (on first login)
When a new `users` row is created via MediaWiki OAuth callback, in the same DB transaction:

1. Read `xp.welcome_grant` from YAML.
2. If `enabled: true`: insert `xp_transactions(user_id=new_user, amount=welcome_grant.amount, reason='welcome_grant', memo=welcome_grant.memo)` and set `xp_balance = welcome_grant.amount`.
3. If `enabled: false`: user starts at 0 XP.

**Idempotency:** enforced by a partial unique index `CREATE UNIQUE INDEX users_one_welcome_grant ON xp_transactions(user_id) WHERE reason = 'welcome_grant'`. A user who is somehow created twice (data repair, etc.) cannot receive a second welcome grant.

**Config-consistency check at startup / SIGHUP:** if `posting_fee.enabled = true` AND (`welcome_grant.enabled = false` OR `welcome_grant.amount < posting_fee.flat_amount`), log a warning to the application log and surface it on `GET /stats` as `economy_warnings: ["..."]`. Does not block startup — admins may have intentional reasons.

### Quest creation cost
On `POST /quests` with `creator_user_id IS NOT NULL`:

1. Compute fee from `xp.posting_fee` config:
   - `flat`: `flat_amount`
   - `proportional`: `ceil(quest.xp * proportional_rate)`
   - `floor_or_proportional`: `max(floor_min, ceil(quest.xp * proportional_rate))`
2. If `creator.xp_balance < fee`: **reject with 402 Payment Required**, body explains the shortfall. Quest is not inserted.
3. In a single DB transaction:
   - Insert quest row with `posting_fee_charged = fee` and `posting_fee_destination` snapshotted from YAML.
   - Insert `xp_transactions(user_id=creator, amount=-fee, reason='quest_posting_fee', quest_id=...)`.
   - If `destination == treasury`: insert `xp_transactions(user_id=treasury_user, amount=+fee, reason='quest_posting_fee_treasury', quest_id=...)`.
   - Update creator balance (and treasury if applicable).

Service-principal posts (creator_user_id IS NULL) skip steps 1–3 when `service_principal_exempt: true`. The quest row records `posting_fee_charged = 0`, `posting_fee_destination = NULL`.

If `enabled: false`: same as exempt — `posting_fee_charged = 0`, no ledger rows.

### Quest payout
Triggered when status transitions to its terminal state (`done` if no verification required, `verified` if it is). All inserts in one DB transaction:

1. For each active claimer: insert `xp_transactions(amount=quest.xp, reason='quest_completion')`.
2. Compute `boost_pool = sum(quest_boosts.amount where refunded_at IS NULL)`.
3. For each active claimer: insert `xp_transactions(amount=floor(boost_pool / N_claimers), reason='quest_completion', boost_id=NULL, memo='boost share')`. **Integer remainder is dropped** (mildly deflationary, predictable; surfaced in `GET /economy` so consumers know).
4. If `creator_user_id IS NOT NULL`: insert `xp_transactions(amount=creator_bonus_xp, reason='quest_creation_bonus')`.
5. If transition is to `verified` and `verifier_bonus_xp > 0`: insert `xp_transactions(amount=verifier_bonus_xp, reason='verifier_bonus', user_id=verifying_user)`.
6. Update each affected user's `xp_balance`.
7. Set `quests.paid_out_at = now()`.

### Quest boost (`POST /quests/{id}/boost`)
- Caller must be authenticated.
- Quest must not be `paid_out_at IS NOT NULL` and not `deleted_at IS NOT NULL`.
- `is_self_boost = (caller == quest.creator_user_id)`. If `self_boost_policy == disallowed`, reject. If `allowed_flagged`, surface in response.
- Insert `xp_transactions(amount=-N, reason='quest_boost_spend', quest_id=...)`.
- Insert `quest_boosts(...)` referencing that ledger row.
- CHECK on user balance enforces no overspend.

### Level up (`POST /me/level-up`)
- Caller must be authenticated.
- Compute `next_cost` from YAML curve at user's current level.
- If user.balance < next_cost or user.level >= max_level, reject.
- Insert `xp_transactions(amount=-next_cost, reason='level_up_spend')`.
- Increment `users.level`.

### Soft-delete + refunds
On `DELETE /quests/{id}` (creator or admin), set `deleted_at`. Two refund paths apply:

**Boost refunds** (`xp.boost_refund_on_delete`):
- `always`: refund every boost.
- `never`: refund nothing.
- `deleter_neq_booster` *(default)*: refund every boost where `booster_user_id != deleter_user_id`. Self-boosts where the booster is the deleter are burned.

Each refund inserts `xp_transactions(amount=+N, reason='quest_boost_refund', boost_id=...)` and updates the booster's balance and the boost row's `refund_txn_id` / `refunded_at`.

**Posting fee refunds** (`xp.posting_fee.refund_on_delete`):
- `never` *(default)*: posting fee stays burned/in treasury.
- `if_unclaimed`: refund only when the quest has zero active claims at delete time.
- `always`: refund unconditionally.

A refund inserts `xp_transactions(user_id=creator, amount=+posting_fee_charged, reason='quest_posting_fee_refund', quest_id=...)` and, if the original destination was treasury, a paired negative on the treasury user. The quest row remains soft-deleted.

### Reopen
Disallowed once `paid_out_at IS NOT NULL`. Use `POST /quests/{id}/clone`.

### Soft-delete visibility
- List endpoints (`GET /quests`, `GET /quests/{id}/boosts`, etc.) filter `deleted_at IS NULL` for unauthed callers.
- `GET /quests/{id}` for a soft-deleted quest returns **410 Gone** to unauthed callers, with a minimal body: `{"error": "deleted", "deleted_at": "..."}`.
- Authed callers with `admin` scope can pass `?include_deleted=true` to opt back into seeing deleted rows on list and detail.
- Soft-deleted quests still appear in the ledger via `quest_id` FKs; ledger reads are not affected by `deleted_at`.

### Donor bounties

**Pledge** (`POST /quests/{id}/bounty`):
- Caller may be authed user or anonymous (anonymous requires `donor_display_name` and a Stripe payment-method token).
- Quest must not be `paid_out_at IS NOT NULL` and not `deleted_at IS NOT NULL`.
- Authorize-only on Stripe; store `stripe_payment_method_id` for later capture. No charge yet.
- Insert `quest_bounties` row, bump `quests.total_bounty_cents` and `quests.bounty_count`.

**Collection** (on terminal-payout transition):
- For each active pledge on the quest, capture via stored `stripe_payment_method_id`.
- On success: set `collected_at`, store `stripe_payment_intent_id`.
- On failure: log to `internal_notes`, mark pledge `withdrawn_at = now()` with memo, do not block the quest payout. NB loses a pledge but the quest still completes.
- Recompute denormalized totals on `quests`.

**Withdraw / expire**:
- `DELETE /quests/{id}/bounty/{bounty_id}` by the original donor or admin → set `withdrawn_at`, recompute denormalized totals.
- A background sweep marks `withdrawn_at = expires_at` on pledges whose `expires_at < now()` and quest still open. v1 ships without the sweep job; do it manually via admin endpoint until volume justifies.

**Quest soft-delete** with active pledges: set `withdrawn_at` on all active pledges in the same transaction. Pledges are never charged on deleted quests.

### Claim completion (`POST /quests/{id}/done`)

The `done` endpoint accepts per-claimer completion data and is the natural place to capture reporting:

Request body (per caller, applies to their own `quest_claims` row):
```json
{
  "time_spent_minutes": 18,
  "done_state": "full",
  "claim_notes": "...",
  "attachment_ids": [123]
}
```

- Caller must hold an active claim on the quest.
- Required: `time_spent_minutes`, `done_state`.
- Optional: `claim_notes`, `attachment_ids` (references to previously-uploaded `quest_attachments` rows with `scope='claim'`).
- Updates the caller's `quest_claims` row: sets `time_spent_minutes`, `done_state`, `claim_notes`, `reported_at = now()`.
- Quest-level transition to `done` (and subsequent payout) fires when **all active claimers** have submitted, or when the quest creator/verifier explicitly closes it via `POST /quests/{id}/close` (admin or creator scope).
- `done_state = 'partial'` or `'blocked'` does not auto-transition the quest; it remains `claimed` with the report visible. Creator/admin chooses whether to mark complete, leave open for further work, or clone.

### Quest payout (extended)

Step 0 (new), before the existing payout steps: collect all active `quest_bounties` for this quest (see Donor bounties → Collection above). Bounty collection failures do **not** block XP payout.

### Civic-hours certificate

Noisebridge is establishing a program with the City of San Francisco whereby volunteer hours at NB can be applied toward parking-ticket debt and similar civic obligations. The Quest Board's per-claimer time data is the substrate; this subsection defines what NB issues to the City.

**Trust model.** No in-system certifier role, no real-name binding, no ID-check at claim time. The full strength of the certification rests on the §1 principle that wiki accounts are issued only after in-person admin verification. Every claim is bound to a wiki_username, and every wiki_username was vouched for face-to-face at signup. The certificate states this explicitly so the City can audit the chain.

**No new tables.** The certificate is generated from existing `quest_claims.time_spent_minutes` + `quests` join, scoped by user and date range.

**Certificate contents:**
- NB letterhead, 501(c)(3) statement
- Wiki username (the verified identity)
- Optional display name supplied at generation time (not stored)
- Date range
- Total hours
- Per-quest breakdown (title, date, minutes)
- The verbatim sentence: *"Wiki accounts at Noisebridge are issued only after in-person verification by a Noisebridge administrator. The hours below were reported by [wiki_username], an account so verified."*
- Date of issue
- A signature line for optional board countersignature (no system-side field; ink-on-paper if the City requests stronger proof)

**Self-service generation:** `GET /me/hours/certificate?from=YYYY-MM-DD&to=YYYY-MM-DD&display_name=...&format=html|pdf`. Default format `html`; `pdf` available when the renderer is installed (deferrable past v1).

**Admin generation on behalf of a user:** `GET /users/{id}/hours/certificate?...` with admin scope; same parameters and output. For board members generating certificates at the space for users who didn't bring a device.

**What is *not* included:** no Sybil mitigation in the system itself, no ID check, no civic-hours "certifier" role/scope, no `hour_certifications` table, no pre-emptive flagging of implausible totals. Mitigations, if ever needed, are post-hoc — the board declines to countersign a certificate that looks wrong. The system's job is to surface accurate hour totals; adjudication stays human.

### Status state machine
```
              claim (active claims >= party_min)
   open  ─────────────────────────────────►  claimed
                                                │
                                                │ done
                                                ▼
                              ┌─── if !requires_verification ─── done (PAID OUT, terminal)
                              │
                              └─── if requires_verification  ─── done (pending) ── verify ──► verified (PAID OUT, terminal)
```
No reopen path. Sub-quest `auto` rollup fires only on terminal-paid-out states.

---

## 5. Auth (unchanged)

- **Humans:** MediaWiki OAuth → `/auth/wiki/login` → upsert into `users`, issue session token.
- **Service principals:** `api_keys` table, hashed argon2, scoped (`quests:read`, `quests:write`, `quests:verify`, `admin`). Bearer `sp_<key>`.
- **Discord:** not in v1; columns exist on `users` for opportunistic capture.

---

## 6. Field visibility

| field | public | authed |
|---|---|---|
| id, title, description, status, xp, xp_source, urgency, due_date | ✅ | ✅ |
| guild, location, skills, party_min/max | ✅ | ✅ |
| parent_quest_id, rollup_mode, paid_out_at, done_at, verified_at | ✅ | ✅ |
| creator_attribution (string) | ✅ | ✅ |
| **boost summary**: total_boost_pool, external_boost_pool, self_boost_amount, boost_count | ✅ | ✅ |
| **boost detail list**: per-booster amounts + identities | ❌ | ✅ |
| creator_user_id, creator wiki_username | ❌ | ✅ |
| creator_bonus_xp, verifier_bonus_xp, posting_fee_charged, posting_fee_destination | ❌ | ✅ |
| claims (who/when) | ❌ (count only) | ✅ |
| verifier_user_ids | ❌ | ✅ |
| internal_notes | ❌ | ✅ creator + verifiers + admins |
| **bounty summary**: total_bounty_cents, bounty_count | ✅ | ✅ |
| **bounty detail list**: per-donor amounts, display_name, memo | ✅ when `donor_display_name` set OR donor opted public; else aggregate only | ✅ full detail (includes donor wiki_username) for admins; donors see their own |
| stripe payment ids on `quest_bounties` | ❌ | ✅ admin only |
| **claim completion data**: time_spent_minutes, done_state, claim_notes, reported_at | ✅ | ✅ |
| claim attachments (photos) | ✅ | ✅ |

Users:
- `xp_balance`, `level` — public on `GET /users/{id}` if `leaderboard.show_balances_publicly = true`, else self/admin only.
- Transaction history — authed only; self or admin.

---

## 7. API surface

All paths under `/api/v1/`. JSON. OpenAPI at `/api/v1/docs`.

### Quests
```
GET    /quests                   # cursor-paginated, filterable
GET    /quests/{id}              # public-safe by default; auth → full
POST   /quests
PATCH  /quests/{id}              # blocked once paid_out except internal_notes
DELETE /quests/{id}              # soft-delete; triggers boost-refund logic
POST   /quests/{id}/clone

POST   /quests/{id}/claim
DELETE /quests/{id}/claim
POST   /quests/{id}/done
POST   /quests/{id}/verify

POST   /quests/{id}/boost        # body: { amount: int }; returns updated quest + booster's new balance
GET    /quests/{id}/boosts       # detail list (auth required)

POST   /quests/{id}/bounty       # pledge real $; body: { amount_cents, donor_display_name?, memo?, expires_at?, stripe_payment_method_id }
GET    /quests/{id}/bounties     # public summary; detail (donor identity) requires auth
DELETE /quests/{id}/bounty/{bounty_id}  # withdraw (donor or admin)

POST   /quests/{id}/close        # creator/admin force-close when claimers are partial/blocked or stop reporting

POST   /attachments              # multipart upload; returns { id, url, mime_type }; body declares scope + quest_id (+ claim_user_id when scope='claim')

POST   /quests/draft             # LLM preview, no DB write
```

### Identity & XP
```
GET    /me
GET    /me/xp                    # cursor-paginated transaction history + current balance
GET    /me/hours/certificate     # civic-hours cert; params: from, to, display_name?, format=html|pdf
POST   /me/level-up              # spends XP, advances level

GET    /users/{id}
GET    /users/{id}/xp            # self or admin
GET    /users/{id}/hours/certificate  # admin scope; same params as /me variant

GET    /auth/wiki/login
GET    /auth/wiki/callback
POST   /auth/logout

POST   /admin/xp/grant           # admin scope
POST   /admin/xp/correct         # admin scope
```

### Taxonomy
```
GET    /guilds                   # offset-paginated or unpaginated (small list)
GET    /locations
POST   /guilds, /locations       # admin
```

### Meta
```
GET    /healthz
GET    /version
GET    /stats                    # public: quest counts, total XP minted, total volunteer-minutes reported, total bounty cents collected, calibration status, current effective economy config (public-safe portions)
GET    /economy                  # public: returns the active YAML (public-safe portions) so consumers know the rules
```

### Pagination
- **Cursor** on `/quests`, `/me/xp`, `/users/{id}/xp`, `/quests/{id}/boosts`. Cursor is opaque base64 of `(sort_key, id)`.
- **Offset** (or unpaginated) on `/guilds`, `/locations`, taxonomy lookups.

---

## 8. LLM assist (`/quests/draft`)

Same shape as before. Returns `xp_suggested` only when `calibration_status == 'calibrated'` (gold-standard set ≥ `xp.llm_xp_suggestion.threshold_quests`). Suggested XP comes from `qwen2.5:7b` few-shot-prompted with `xp.llm_xp_suggestion.few_shot_sample_size` random gold-standard `(description, xp)` pairs.

---

## 9. Out of scope for v1

- Discord integration (linking, slash commands, bot service principal).
- XP decay / seasonal resets.
- Reputation, badges, level *names* (level is just an int; UI can map to titles).
- Notifications / webhooks.
- Full-text search (use `ILIKE` for now).
- Quest templates.
- Reverting non-terminal status transitions (claim/done before payout) via API — admin DB action only.
- Audit log beyond timestamp columns and the ledger.
- Rate limits.

- 501(c)(3) year-end donor acknowledgment letters from `quest_bounties` history (schema supports it; generator deferred).
- Background sweep job for `quest_bounties.expires_at` (manual admin endpoint in v1).
- Bounty matching ("I'll match the first $100 on quests tagged `accessibility`").
- Bounty stacking caps (none in v1; sum + display top donors).

### Future goals (post-v1, design hooks)

- **Wiki user-page badges.** Provide an endpoint set that MediaWiki templates / extensions can embed on a user's wiki page to render their quest-board status (level, XP, quest count, recent activity).
  - Anticipated shape:
    - `GET /api/v1/users/by-wiki/{wiki_username}/badge.svg` — server-rendered SVG badge (XP / level / quests done). Cacheable. No JS required on the wiki side.
    - `GET /api/v1/users/by-wiki/{wiki_username}/badge.json` — raw data for client-side or template-side rendering.
    - `GET /api/v1/users/by-wiki/{wiki_username}/badge.html` — small inline HTML snippet for `{{#fetch:...}}`-style template patterns if the wiki has the right extension.
  - Cache headers (`Cache-Control: public, max-age=300`) so the wiki isn't hammering the API on every page render.
  - The API needs a canonical, public-stable URL pattern keyed on `wiki_username` — note it as a v1 design constraint so the URL space doesn't have to break later.

---

## 10. Deployment

See [DEPLOYMENT.md](./DEPLOYMENT.md) for the full runbook: service user setup, MediaWiki OAuth consumer registration, Postgres, systemd unit, nginx + Let's Encrypt, backups, and pre-launch checklist.
