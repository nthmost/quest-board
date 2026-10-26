---
id: docs-convention
title: Design-docs information architecture
type: reference
status: shipped
created: 2026-10-26
updated: 2026-10-26
owners: [nthmost]
tags: [meta, docs, architecture]
---

# Design-docs information architecture

How design knowledge is organized in this repo so that **what's true now**,
**what we've committed to build**, and **what we might (or decided not to) do**
each have a distinct home — readable by humans and LLMs, and renderable as a
graph by an external app.

This exists because prose drifts. An idea that gets dropped leaves no trace
except an old assertion it now contradicts (see the multi-character and
civic-hours churn in the git history). The fix: **status is a first-class
field, and rejected/deferred ideas are kept, not deleted.**

---

## The model: every doc is a typed node in a graph

One Markdown file = one **node**. Its YAML frontmatter is the machine-readable
contract; the body is for humans/LLMs. Relationships between docs are **typed
edges** declared in frontmatter. `scripts/build_docs_index.py` walks every
doc's frontmatter and emits [`index.json`](./index.json) — a `{nodes, edges}`
graph that an LLM can read without opening every file, and that a viewer
(Cytoscape / D3, or Obsidian via wikilinks) can draw. Each node also carries a
`body` (an inline preview of the doc's prose) and a `source` link (the
originating document on GitHub, with a section anchor inferred from the `reason`
— e.g. `SPEC §3` → `#3-economy-yaml`), so both views can lead from a node into
its full description and the document it came from.

Four things do the work: `type`, `status`, edges, and the generated index.

---

## `type` — what role a doc plays

| type | role | lives in |
|---|---|---|
| `reference` | how it works **right now** | repo root (UI.md), `docs/` |
| `spec` | intended long-term design | repo root (SPEC.md, DEMO.md) |
| `status` | time-stamped "now" snapshot | controller dir (STATUS.md) |
| `runbook` | ops / deployment | controller dir (DEPLOYMENT.md) |
| `decision` | a choice made — an ADR; immutable, superseded not edited | `docs/decisions/` |
| `proposal` | a fleshed-out idea under consideration — an RFC | `docs/proposals/` |
| `feature` | a shipped capability — lightweight registry node | `docs/features/FEATURES.md` |
| `idea` | a raw "maybe," not yet worked out | `docs/ideas/BACKLOG.md` |
| `note` | dated exploration / rationale | repo root, `docs/notes/` |

> **Decision vs proposal:** a `proposal` is still a question ("should we build
> X?"). A `decision` is the answer, recorded once and not rewritten. When a new
> decision reverses an old one, the old file stays and gains
> `status: superseded` + `superseded_by`.

---

## `status` — the lifecycle that lets "maybe" exist

```
idea → exploring → proposed → accepted → building → shipped
                      ↘ deferred     ↘ rejected     ↘ superseded
```

| status | meaning |
|---|---|
| `idea` | captured, not yet evaluated |
| `exploring` | being fleshed out; open questions remain |
| `proposed` | fleshed out, awaiting a decision |
| `accepted` | decided — we will build it (may not be built yet) |
| `building` | in progress |
| `shipped` | built and reflected in the reference docs |
| `deferred` | good idea, **not now** — parked with a `reason` |
| `rejected` | decided against — **kept** with a `reason`, so we don't relitigate |
| `superseded` | replaced by a newer node named in `superseded_by` |

The last three are the point. `deferred`, `rejected`, and `superseded` nodes
are never deleted — they are how "we changed our mind" stays legible instead of
rotting into a contradiction.

---

## Edges — the relationships that make it a graph

Declared as frontmatter fields whose values are **node ids** (not file paths):

| field | meaning |
|---|---|
| `supersedes` / `superseded_by` | this node replaces / was replaced by another |
| `depends_on` | needs another node done/decided first |
| `blocks` | this node is blocking another |
| `relates_to` | soft link, same area |
| `realizes` | an implementation node that fulfills a spec node |

Only point edges at **real nodes** (ids that exist as files). Rejected
*alternatives* that were never their own doc are recorded in the body prose, not
as dangling edges. The generator flags any edge whose target id doesn't exist.

---

## Frontmatter schema

```yaml
---
id: civic-hours-cert           # stable kebab-case slug = the node id (required)
title: Civic-hours certificate # human title (required)
type: proposal                 # see type table (required)
status: deferred               # see status table (required)
created: 2026-05-19
updated: 2026-10-26
owners: [nthmost]
tags: [identity, economy, verification]
depends_on: [personhood-verification]
relates_to: [spec, local-auth]
superseded_by: []
reason: "self-serve signup broke the in-person verification chain"
---
```

`id`, `title`, `type`, `status` are required. Everything else is optional; edge
fields default to empty. `reason` is strongly encouraged on `deferred` /
`rejected` / `superseded` nodes — it's the single most useful field for the next
reader.

---

## Layout

```
quest-board/
├── README.md            # type: reference  (project overview / map)
├── SPEC.md              # type: spec        (long-term design)
├── DEMO.md              # type: spec        (demo delta on SPEC)
├── UI.md                # type: reference   (shipped visual/route reference)
├── TEST_PERSONAS.md     # type: note
├── DESIGN_NOTES_*.md    # type: note
└── docs/
    ├── README.md        # ← this file (the convention)
    ├── index.json       # generated: {nodes, edges}
    ├── decisions/       # ADRs — NNNN-slug.md, immutable once accepted
    ├── proposals/       # RFCs — slug.md, one node each
    ├── features/
    │   └── FEATURES.md   # shipped capabilities as a table (lightweight nodes)
    ├── ideas/
    │   └── BACKLOG.md    # raw maybes as a table; graduate to a proposal when real
    └── notes/           # dated explorations (optional home; root is also fine)
```

Operational docs (`STATUS.md`, `DEPLOYMENT.md`, `ANSIBLE_future.md`) live one
level up in the Actropolis controller dir and are *referenced* here but not
indexed — the index is repo-scoped for now.

---

## Registry tables — features & ideas

Two files carry **lightweight nodes as table rows** instead of one file each, so
the graph stays complete without a file per shipped feature or raw idea:

- `docs/features/FEATURES.md` — shipped capabilities (`type: feature`).
- `docs/ideas/BACKLOG.md` — raw maybes (`type: idea`).

The generator parses each file's first pipe-table; the `id` column keys the node,
and `status` / `reason` / edge columns (`relates_to`, `depends_on`, …) fill it in.
When a row grows real design tension, promote it to a `decisions/` or `proposals/`
file with the **same `id`** — the detail file wins and the row is ignored (the
generator reports the shadowed id as a `duplicate_ids` note).

## How to add a node

- **A raw maybe** → add a row to `docs/ideas/BACKLOG.md`. No file yet.
- **An idea worth designing** → `docs/proposals/<slug>.md`, `type: proposal`,
  `status: proposed` (or `exploring`). Promote it out of BACKLOG.
- **A choice you're making** → `docs/decisions/<NNNN>-<slug>.md`,
  `type: decision`, `status: accepted`. If it reverses an earlier decision, set
  the old one's `status: superseded` + `superseded_by: <new-id>` and the new
  one's `supersedes: <old-id>`. Record rejected alternatives in the body.
- **When something ships** → flip the node to `status: shipped` and update the
  relevant `reference` doc so "now" stays accurate.

Then regenerate the index:

```bash
python -m scripts.build_docs_index   # writes docs/index.json
```

---

## How it's consumed

- **Humans** read the body; scan `docs/decisions/` and `docs/ideas/BACKLOG.md`
  to see what's settled vs open.
- **LLMs** read `index.json` first to get the lay of the land — especially which
  ideas are `deferred`/`rejected` and *why* — before trusting any one doc.
- **A viewer app** reads `index.json` (`nodes` + `edges`) directly. The shape is
  generic enough for Cytoscape/D3; if you open the repo in Obsidian, the same
  relationships render as a graph when edges are also written as `[[wikilinks]]`
  in the body.

The generator also emits a **textual** rendering of the same graph for people
who'd rather read than explore visually:

- `docs/OVERVIEW.md` — a grouped Markdown outline (by type, then status, with
  reasons and edges). Regenerated every build; readable in-repo, on GitHub, and
  by LLMs.
- `docs/overview.html` — the same outline in the browser, with a text filter;
  cross-linked with `graph.html` (the visual view). Both read `index.json`.
