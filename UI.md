# Quest Board — UI Reference

> **Orientation:** Front-end visual reference — palette, panel system,
> component vocabulary, page-by-page layout. Snapshot of the live state at
> <https://nbprogressquest.nthmost.net/> as of 2026-05-09. Living document; update
> when the visual register or component vocabulary changes.
> If you're brand new, start with [README.md](./README.md).

## 1. Stack & file layout

- **Server-rendered Jinja2 templates**, no SPA. FastAPI returns full pages.
- **htmx + SSE** anticipated for live-update surfaces (activity feed, character sheet) once the simulator lands. Not used yet.
- **Static CSS only** at `app/static/css/nes.css`. No JS framework, no preprocessor.
- Cache-buster: every page link to the CSS includes `?v=<mtime>`, computed once at app startup from the file's mtime. Browsers re-fetch automatically when the CSS changes — no hard-reload needed.

```
app/
├── templates/
│   ├── base.html               # html shell + asset_v cache buster + footer
│   ├── index.html              # /
│   ├── login.html              # /login
│   ├── me_characters.html      # /me/characters
│   ├── me_character_new.html   # /me/characters/new
│   ├── admin_layout.html       # admin shell
│   ├── admin_dashboard.html    # /admin/
│   ├── admin_quests.html       # /admin/quests
│   ├── admin_users.html        # /admin/users
│   └── admin_templates.html    # /admin/templates
└── static/
    └── css/nes.css             # all styles
```

---

## 2. Aesthetic decisions

Anchored on the **NES / Press Start 2P** register established by
`dumps.nthmost.net`. Color and font choices are deliberate; keep the
register consistent when adding new pages.

### Palette (CSS custom properties)

| Var | Hex | Used for |
|---|---|---|
| `--nes-black` | `#0c0c0c` | page background |
| `--nes-dim` | `#1a1a1a` | inset surfaces, list-item backgrounds |
| `--nes-grey` | `#585858` | borders, dim text, scrollbar thumb |
| `--nes-grey-2` | `#303030` | panel-header background, dividers |
| `--nes-brown` | `#88401c` | title-bar borders, brown panels |
| `--nes-orange` | `#e87400` | open-quest panel, target text in feed |
| `--nes-red` | `#c82020` | errors, retire-button hover |
| `--nes-yellow` | `#fcd058` | titles, XP, primary CTAs, accent text |
| `--nes-tan` | `#fcc49c` | secondary text, dim labels |
| `--nes-white` | `#fcfcfc` | body text, default panel border |
| `--nes-green` | `#30a830` | active character, "DONE" events, growth metrics |
| `--nes-blue` | `#6888fc` | activity feed panel, "CLAIMED" event accents |

### Typography

- **Press Start 2P** is *only* used for: `title-bar h1`, panel headers, stat keys/values, big stat numbers, bar labels, chips, footer, the time chip on activity feed events. Anywhere it's used, font sizes stay between 8–14px to remain readable.
- **VT323** is the default body face at **20px / 1.4 line-height**. Used for: prose, character names, quest titles, full activity-feed text, descriptions, login form inputs, big stats.
- Both fonts loaded from Google Fonts via `<link>` in `base.html`.
- Use `.psp` utility class to opt into Press Start 2P selectively.

### Body texture

Body has a subtle CRT-scanline background using `repeating-linear-gradient` (every 4px, 2% white). It reads as ambient texture, not noise.

---

## 3. Layout shell

`base.html` provides `.shell` (max-width 1100px, vertical flow) plus a `.footer`. Every concrete page extends `base.html` and writes its own `{% block content %}`.

### Title bars

`.title-bar` (4px brown border, dim background, centered):
- `h1` — page title in Press Start 2P 22px yellow with letter-spacing
- `.sub` — Press Start 2P 9px tan caption underneath
- `.title-auth` — right-aligned strip with login state. Renders **LOG IN ▸** when anonymous, or **`<username>` MY CHARACTERS ADMIN LOG OUT** when authenticated. `is_admin` flag controls the ADMIN link.
- `.blink` span animates a single character on/off every 1.2s.

Admin pages use `.admin-title` for a denser variant: smaller h1, a centered nav strip with `DASH / QUESTS / USERS / POOL`.

---

## 4. The panel system

Almost every visual unit is a `.panel`:

```html
<div class="panel panel-{color}">
    <div class="panel-header">★ HEADER</div>
    <div class="panel-body">…content…</div>
</div>
```

- Default: 4px white border on black background
- `.panel-orange / .panel-yellow / .panel-blue / .panel-green / .panel-brown` override the border color
- `.panel-header` is a grey-2 strip with Press Start 2P 10px yellow uppercase text and a 2px grey divider underneath
- `.panel-body` provides 1rem padding (cards in the character grid bump this to 1.4–1.6rem)

---

## 5. Page-by-page reference

### `/` — front-page landing

Vertical flow:

1. **▲ WORLD STATE** (full-width, brown) — four `world-stats` tiles: ADVENTURERS, QUESTS POSTED, XP MINTED, CALIBRATION. Caption + giant number per tile.
2. **Char sheet (1/3) | Open quests (2/3)** row. The character panel has three render branches:
   - Logged in + has a non-deleted character → real character sheet (see §6)
   - Logged in, no character → "Adventure awaits" + ► CREATE CTA
   - Not logged in → "Log in with your Noisebridge wiki account" + ► LOG IN
3. **♦ OPEN QUESTS** (orange panel) is the sibling: 2-column responsive grid (`.quest-grid`), each card has a 21px VT323 title and a Press Start 2P meta strip (`XP / guild / urgency / party`).
4. **⌬ ACTIVITY** (blue panel, full-width below) — `.feed` list. Each `<li>` has a 4px left-border color-coded by event type (`event-claim / event-done / event-level / event-post`), Press Start 2P timestamp chip, baseline-aligned VT323 body. XP badges are a separate Press Start 2P green chip.

### `/login`

Single yellow panel inside `.login-shell`. Big VT323 inputs (22px) with grey borders that turn yellow on focus, a Press Start 2P yellow `► START` button, a tan-on-dashed-divider note explaining the forwarded-once password handling and pointing at `Special:RequestAccount`.

### `/me/characters`

`.char-grid` — auto-fill `minmax(420px, 1fr)`, gap 1.4rem.

Each card:
- `.panel.charsheet` with `.panel-yellow` (inactive) or `.char-active` (active)
- Header reads `★ LV {N} · {CLASS}` on inactive, `♦ ACTIVE · LV {N} · {CLASS}` on active. Active panels have a green header background, green border, and a subtle green outer glow.
- `.name` = VT323 18px yellow
- `.class` = Press Start 2P 9px tan, includes guild name when present
- `.stats` = 2-column grid (key right-aligned in tan PS2P 9px, value left-aligned in white VT323 22px)
- **Skull-and-crossbones retire button (`☠`)** sits in the bottom-right corner. 38×38, tan border at rest, scales up + turns red on hover. Submits to `/me/characters/{id}/delete` via a confirmation dialog.
- **`MAKE ACTIVE`** yellow button below stats appears only on inactive cards. Submits to `/me/characters/{id}/activate`.
- An empty slot (`.char-slot-empty`) appears at the end of the grid until the user hits `demo.max_characters_per_user` (default 4). It's a dashed grey rectangle with `＋ NEW CHARACTER` that turns yellow on hover.

### `/me/characters/new`

Same `.login-shell` layout as `/login`. Three fields: `name` (text), `class_slug` (select with each option's name + flavor tag), `primary_guild_id` (select, optional). Yellow `► CREATE` submit. On error, the panel re-renders with the values preserved and `.login-error` ▼-prefixed at the top.

### `/admin/{,quests,users,templates}`

All four pages extend `admin_layout.html`. Shared title bar + DASH/QUESTS/USERS/POOL nav. Visual register is denser:

- `.adm-table` — 18px VT323 body, 9px Press Start 2P uppercase headers with letter-spacing. Hover row highlights yellow at 4% opacity. Columns: `.hi` (yellow titles), `.dim` (tan dates), `.num` (monospace numbers), all `white-space: nowrap` to prevent date wrapping.
- `.kv-grid` — 2-column mini-grid for stats: tan PS2P labels left, big PS2P numbers right.
- `.chip` (Press Start 2P 8px yellow border) on the dashboard, `.chip-mini` (VT323 17px tan) on the templates page.
- `.adm-filters` — inline form: PS2P 8px tan labels, VT323 18px selects with grey borders, yellow `APPLY` and `CLEAR` buttons.

The dashboard composes ▲ COUNTS + ♦ SEED POOL on top, ⌬ RECENT USERS + ♣ RECENT QUESTS below. The Quests and Templates pages put filters above their table.

---

## 6. Component vocabulary

### Character sheet (`.charsheet`)

The defining component. Same layout on the front page and inside character cards.

- `.name` — VT323 yellow, large (front: 14px PS2P, card: 18px VT323)
- `.class` — Press Start 2P 9px tan uppercase, single line, optionally includes guild name
- `.stats` — 2-column grid, label/value pairs
- `.bar` + `.bar-fill.xp` — XP-to-next-level progress (gradient orange→yellow)
- `.bar` + `.bar-fill.task` — current-task progress (solid blue)
- `.bar-label` — Press Start 2P 8px tan, `space-between` for left label + right percent
- `.now` block — top dashed-divider, VT323 verb/target text, second progress bar for the active task

### Quest grid (`.quest-grid`)

2-column responsive grid (collapses to 1-col under 700px) used inside the front-page `/` Open Quests panel.

- Each `<li>` is a dim-bg card with a 2px grey border that turns yellow on hover
- `.qtitle` — VT323 21px white
- `.qmeta` — flex row of Press Start 2P 8px chips: `.xp` (yellow), `.guild` (green), `.urgent` (red), party-size

### Activity feed (`.feed`)

Full-width below the char/quest row. Each event:
- 4px left border color-coded by `event-type`
- Press Start 2P 10px grey timestamp at the start, baseline-aligned with VT323 23px body
- `.who` (yellow uppercase), `.verb` (white), `.target` (orange), `.xp` (green PS2P 11px chip)

### Buttons

- `.login-button` — yellow PS2P 12px on yellow background, slight scale on press. Used for primary form submits (login, create character).
- `.adm-button` — yellow PS2P 9px, denser. Used in admin filters.
- `.char-activate-btn` — yellow PS2P 9px, sized to fit cards. Inactive characters only.
- `.char-trash` — 38×38 corner button, tan border, ☠ glyph. Bottom-right of every character card.
- `.auth-link` — title-bar text link, PS2P 9px. Used for nav and logout.

### Empty states

- `.empty-board` — Press Start 2P 11px tan, centered `※ MESSAGE ※` block with vertical padding. Used in Quests / Users / Templates lists.

---

## 7. State, auth, navigation

- **Sessions**: Starlette `SessionMiddleware` with a 14-day signed cookie. Secret in `~/projects/nthmost-systems/.secrets/questboard-session.env`.
- **Login**: classic MediaWiki `action=login` against `https://www.noisebridge.net/api.php`. Username + password forwarded once, password discarded. Same pattern as `riseup-meetingnotes/web/auth.py`.
- **Auth context**: every page that needs identity calls `current_username(request)` and `is_admin(username)` to decide title-bar variants and gated routes. `require_login` and `require_admin` are FastAPI deps used on `/me/...` and `/admin/...` respectively.
- **Active character**: `users.active_character_id` (nullable FK). Set automatically on first character creation; reassigned to the next-oldest non-deleted character if the active one is retired; cleared if no characters remain. The front page reads from this column to pick the featured sheet.
- **Cache busting**: `request.state.asset_v` injected via a tiny middleware in `app/main.py` and substituted into the CSS link in `base.html`. Any update to `app/static/css/nes.css` bumps the value at next service start.

---

## 8. Patterns to keep using

- **Add a panel, pick a color**: `panel panel-{color}` + a `panel-header` + a `panel-body`. Don't invent new container vocabularies for new pages.
- **Press Start 2P only for accents**: anything that's prose or runs longer than ~3 words → VT323. Anything labelled, numeric, or chip-shaped → Press Start 2P.
- **Density**: front-page is generous (1rem padding, 18-22px body); admin is denser (smaller text, tight rows). Don't mix the two on a single page.
- **Color-code event/state types**: yellow = primary/value, orange = action target, green = success/active, blue = claimed/in-flight, red = destructive only on hover, grey = ambient/dim.
- **No hover-only affordances** for primary actions. The skull retire button is visible at rest; it just doesn't *demand* attention.

---

## 9. Routes that the UI calls

| Method | Path | Purpose |
|---|---|---|
| GET | `/` | landing |
| GET | `/login` | login form |
| POST | `/login` | submit credentials |
| POST | `/logout` | drop session |
| GET | `/me/characters` | character cards |
| GET | `/me/characters/new` | new-character form |
| POST | `/me/characters` | create |
| POST | `/me/characters/{id}/activate` | mark active |
| POST | `/me/characters/{id}/delete` | soft-delete |
| GET | `/admin/` | dashboard |
| GET | `/admin/quests` | quests table |
| GET | `/admin/users` | users table |
| GET | `/admin/templates` | seed pool |
| GET | `/static/css/nes.css?v={mtime}` | styles |

API routes (`/api/v1/*`) are documented in SPEC.md §7; this file is concerned only with the human-facing pages.

---

## 10. Open visual TODOs (when the simulator lands)

- **Activity feed → live SSE**. Replace the static `_mock_feed()` in `app/routes/pages.py` with `EventSource`-driven dispatch. Likely an htmx `sse-swap` pattern keyed by event type.
- **Character sheet → live progress bars**. The `.bar-fill.task` width is currently 0%; once active claims have a `mature_at`, the front-page sheet updates the bar via SSE every tick.
- **"NOW" block on the active character** should reflect the simulator's current verb/target/timer. Today it just says `RESTING` / `(no quest claimed)`.
- **Per-character page** (`/c/{id}`) for public-facing character profiles. URL space is reserved; not yet built.
- **Leaderboard** (`/leaderboard`). Page reserved; needs a sort + a small podium component.

---

## 11. Anti-patterns observed and avoided

- ❌ **Press Start 2P at body density**. Looks like a captcha; switched to VT323 at 18-23px for prose.
- ❌ **Aggressive DELETE buttons**. Replaced with a corner skull-and-crossbones that's visible but not demanding.
- ❌ **Inline styles for repeated patterns**. Stat panels were inlined originally; now factored into `.world-stats` / `.ws-label` / `.ws-num`.
- ❌ **Cards that hide level info on the active state**. Header reads `♦ ACTIVE · LV N · CLASS` so both signals coexist.
- ❌ **Pretending the admin and front pages share visual density**. They don't; admin gets its own denser type stack via `.adm-*`.
