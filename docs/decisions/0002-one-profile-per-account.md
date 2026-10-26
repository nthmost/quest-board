---
id: one-profile-per-account
title: One profile per account (both modes)
type: decision
status: shipped
created: 2026-10-15
updated: 2026-10-26
owners: [nthmost]
tags: [identity, characters, demo]
relates_to: [spec, demo]
---

# One profile per account (both modes)

## Status
Shipped — `create_default_profile` runs at signup; there is no
`/me/characters/new`, `/activate`, or `/delete` flow. `/me/characters` is the
single "YOUR PROFILE" editor.

## Context
The original demo design (see DEMO.md history) let a player create **up to 4
characters** per account and watch them auto-play, with the "real" tool
constraining this to 1:1 via config. Carrying two identity cardinalities doubled
the surface area of every character-scoped feature (claims, XP ledger, active
selection, UI).

## Decision
**One profile per account, in both the demo and the real tool.** The profile is
a single `characters` row created at signup and pointed to by
`users.active_character_id`. Identity splits into three names on the account:
`username` (login, fixed), a freely-changeable **visible name**, and a private
`real_name` + `show_real_name` toggle (migrations `0010`, `0011`).

## Rejected alternatives
- **Up to 4 characters in the demo (multi-character).** Dropped — the extra
  cardinality wasn't worth the complexity, and a single profile still delivers
  the Progress-Quest auto-play feel.

## Consequences
- "Character" and "profile" are now the same single per-account row; docs use
  "profile."
- The multi-character UI affordances (`MAKE ACTIVE`, the `☠` retire button,
  empty slots, `demo.max_characters_per_user`) are retired.
- The visible-name vs real-name split addresses the "name doesn't match
  preferred name" persona without needing multiple characters.
