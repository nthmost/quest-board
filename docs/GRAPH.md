# Graph subdomain — maintenance directive

> Governs **graph.actropolis.org** (the design-docs feature graph + text view)
> and the contract that keeps it in sync with the quest-board docs, both ways.
> First-time server setup lives in [`graph-deploy.md`](./graph-deploy.md); the
> IA itself is defined in [`README.md`](./README.md).

## Source of truth

- The **repo docs are canonical.** `graph.actropolis.org` serves a *build
  artifact* (`graph.html`, `overview.html`, `index.json`) generated from them.
- `docs/index.json` and `docs/OVERVIEW.md` are **generated** by
  `scripts/build_docs_index.py`. Never hand-edit them, and never edit the files
  under `/var/www/graph.actropolis.org/` on zephyr — the next publish overwrites
  both.

## The invariant (both directions)

Docs and graph must never drift.

1. **Docs change → republish the graph.** Any of these requires a publish:
   editing a doc's frontmatter or body; adding/retiring a `decisions/` or
   `proposals/` file; adding or editing a row in `docs/features/FEATURES.md` or
   `docs/ideas/BACKLOG.md`; changing any node's status or edges.
2. **Graph change → update the docs.** Changing the viewers
   (`graph.html` / `overview.html`), the generator
   (`scripts/build_docs_index.py`), or the node model means updating the
   convention in [`README.md`](./README.md) **in the same change**, then
   republishing. The graph's behavior and its spec move together.

## Publish — one command

From anywhere in the repo:

```bash
scripts/publish_graph.sh
```

It regenerates `index.json` + `OVERVIEW.md`, **fails if there are dangling
edges**, deploys the three served files to zephyr, and curls the live URL.
Overrides: `GRAPH_HOST` (default `zephyr`), `PY` (default `.venv/bin/python`).

Then commit the regenerated artifacts so GitHub matches what's live:

```bash
git add -A && git commit -m "docs: <what changed>"   # includes index.json + OVERVIEW.md
```

## Adding or changing a node

- A **raw idea** → a row in `docs/ideas/BACKLOG.md`.
- A **shipped capability** → a row in `docs/features/FEATURES.md`.
- A **decision or proposal worth prose** → a file in `docs/decisions/` or
  `docs/proposals/` (a file's `id` wins over any table row with the same id).
- Edges (`relates_to`, `depends_on`, …) must point at real node ids. The
  generator reports `dangling_edges` and `duplicate_ids`; keep both empty
  (the publish script refuses to deploy on dangling edges).
- Give each row a `reason` that cites its origin (`SPEC §3`, `DEMO §4`): the
  generator turns that into the node's "source document" link + section anchor
  shown in both views.

## "Vice versa" — the graph is read-only downstream

There is no path from the deployed site back into the repo. To change **what**
the graph shows, change the docs and republish. To change **how** it shows
(layout, fields, styling), edit the viewers + the convention and republish.
Never edit the server files or the generated files by hand — that drift is
silently erased on the next publish.

## Checklist — any doc change

- [ ] Edit the doc / registry row / node file.
- [ ] `scripts/publish_graph.sh` — regenerates, validates, deploys, verifies.
- [ ] `dangling_edges` and `duplicate_ids` are empty (script fails on dangling).
- [ ] If the IA or tooling changed, `docs/README.md` reflects it.
- [ ] Commit, **including** the regenerated `docs/index.json` + `docs/OVERVIEW.md`.

## Server facts

`graph.actropolis.org` → zephyr `/var/www/graph.actropolis.org/`, a static
Apache vhost with a Let's Encrypt cert (auto-renew). DNS is a Gandi A record →
`149.28.77.210`. Full setup, re-publish, and teardown steps:
[`graph-deploy.md`](./graph-deploy.md).
