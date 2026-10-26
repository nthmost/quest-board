# CLAUDE.md — quest-board

Working guidance for agents in this repo.

- **Coding conventions:** see [`README.md`](./README.md) → "Coding conventions"
  (tiny functions, imports at top, type hints everywhere, no emoji in code,
  `ruff check app/ scripts/ alembic/versions/` clean).

- **Docs ↔ graph sync — hard rule.** The design docs and the feature graph at
  `graph.actropolis.org` must never drift. After **any** change to:
  - `docs/**` (convention, decisions, proposals, `features/FEATURES.md`,
    `ideas/BACKLOG.md`, the viewers),
  - the root design docs (`SPEC.md`, `DEMO.md`, `UI.md`, `README.md`,
    `TEST_PERSONAS.md`), or
  - `scripts/build_docs_index.py`

  run **`scripts/publish_graph.sh`** (regenerates, validates, deploys) and commit
  the regenerated `docs/index.json` + `docs/OVERVIEW.md`. If you changed the
  graph's behavior or node model, update `docs/README.md` in the same change.
  The full contract — including the reverse direction — is **`docs/GRAPH.md`**.
