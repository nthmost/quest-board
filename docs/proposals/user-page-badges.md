---
id: user-page-badges
title: Embeddable user-page badges
type: proposal
status: proposed
created: 2026-05-19
updated: 2026-10-26
owners: [nthmost]
tags: [api, embed, profile]
relates_to: [spec]
---

# Embeddable user-page badges

## Status
Proposed, not built. SPEC §ext mentions it; this node tracks the decision.

## Summary
An endpoint set any external page (a personal site, a makerspace wiki user-page)
can embed to render an account's quest-board status — level, XP, quest count,
recent activity — as SVG / JSON / HTML.

## Open question — path naming
The original sketch used `/api/v1/users/by-wiki/{username}/badge.{svg,json,html}`.
Now that accounts are local rather than wiki-derived
([`local-auth`](../decisions/0001-local-auth.md)), the `by-wiki` segment is
misleading. Proposed rename: `/api/v1/users/by-username/{username}/badge.*`.
Decide before implementing, since it's a public URL contract.

## Notes
- Cache aggressively at the reverse proxy (the DEPLOYMENT template already sketches
  a `proxy_cache_valid` block for the badge path).
- Server-rendered SVG with a cached variant is the "badge fetcher" persona's need.
