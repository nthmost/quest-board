---
id: personhood-verification
title: Personhood verification for local accounts
type: proposal
status: exploring
created: 2026-10-15
updated: 2026-10-26
owners: [nthmost]
tags: [identity, trust, verification]
blocks: [civic-hours-cert]
relates_to: [local-auth]
---

# Personhood verification for local accounts

## Status
Exploring. This is the **blocker** for anything that certifies a real human's
contribution — most directly the civic-hours certificate.

## Context
When auth proxied to the NB wiki, a `username` was effectively 1:1 with a
vouched-for human, because wiki accounts were issued only after in-person admin
verification. The move to [`local-auth`](../decisions/0001-local-auth.md) made
signup self-serve and **removed that guarantee**. Nothing in the system now
attests that an account is a distinct real person.

## The question
How do we re-establish a "this account is a verified human" signal strong enough
to back civic-hours / volunteer-credit certification, without storing PII at
rest?

## Candidate approaches (unscored)
- **Admin approval of accounts** — a lightweight re-creation of the old gate; an
  admin marks an account verified. Centralizes work on admins.
- **Per-space vouching** — an existing verified member of a makerspace vouches
  for a new account in that space. Scales better; needs a vouch model and
  abuse handling.
- **Tiered trust** — unverified accounts can play; only verified accounts can
  generate a certifiable record. Decouples "play" from "certify."

## Downstream
Resolving this unblocks [`civic-hours-cert`](./civic-hours-cert.md).
