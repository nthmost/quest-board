---
id: local-auth
title: Local accounts instead of wiki SSO
type: decision
status: shipped
created: 2026-10-15
updated: 2026-10-26
owners: [nthmost]
tags: [identity, auth, security]
relates_to: [spec, civic-hours-cert]
---

# Local accounts instead of wiki SSO

## Status
Shipped — migration `0008_password_hash`, `app/local_auth.py`, `app/auth.py`,
routes `/register` `/login` `/logout` `/me/password`.

## Context
The Noisebridge Quest Board originally authenticated by proxying credentials to
the Noisebridge MediaWiki (`action=login` against `noisebridge.net/api.php`,
same pattern as nbarchive). The Actropolis rebrand generalized the product
across multiple makerspaces, where "the NB wiki" is not a shared identity
provider.

## Decision
Accounts are **local**: a username + an Argon2id password hash stored in
`users.password_hash`. Self-serve `/register` and `/login`; password change at
`/me/password`; admin bootstrap/reset via `scripts.set_password`. The wiki login
proxy and `wiki_api.py` were removed.

## Rejected alternatives
- **Keep wiki SSO.** Ties every makerspace to NB's wiki; wrong for a multi-space
  product.
- **MediaWiki OAuth.** The NB wiki has no OAuth extension installed, and it
  carries the same single-provider coupling.

## Consequences
- Signup is self-serve, which **broke the in-person personhood guarantee** that
  wiki accounts used to provide. That guarantee underpinned the civic-hours
  certificate — see [`civic-hours-cert`](../proposals/civic-hours-cert.md) and
  [`personhood-verification`](../proposals/personhood-verification.md).
- `users.wiki_username` was renamed to `username` and `wiki_user_id` dropped
  (migration `0011`).
