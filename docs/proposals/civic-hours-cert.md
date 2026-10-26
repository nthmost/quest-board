---
id: civic-hours-cert
title: Civic-hours certificate
type: proposal
status: deferred
created: 2026-05-19
updated: 2026-10-26
owners: [nthmost]
tags: [identity, economy, verification, civic]
depends_on: [personhood-verification]
relates_to: [spec, local-auth, note-donor-bounties]
reason: "self-serve local signup removed the in-person personhood guarantee the certificate relied on"
---

# Civic-hours certificate

## Status
**Deferred** — blocked on
[`personhood-verification`](./personhood-verification.md). Do not ship
certification until that resolves.

## Summary
Let a contributor generate a printable certificate attesting the volunteer hours
they logged via the quest board — usable for court-ordered community service,
resume/volunteer records, or hours-for-tickets programs. Original design and
rationale: SPEC §4 and
[`note-donor-bounties`](../../DESIGN_NOTES_2026-05-19_donor_bounties_and_claim_reporting.md).

## Why it's deferred (not rejected)
The original design deliberately stored **no** real-name binding and ran **no**
promotion/approval workflow, because it leaned entirely on one external fact:
wiki accounts were issued only after in-person admin verification, so every
claim was implicitly by a vouched-for human. The move to
[`local-auth`](../decisions/0001-local-auth.md) **removed that fact.** Every
assumption in the certificate design that depended on it is now unsupported.

The idea is still good — makerspaces genuinely want this. It is parked until a
personhood signal exists to rebuild the chain on.

## To revive
1. Land a [`personhood-verification`](./personhood-verification.md) approach.
2. Re-derive the certificate's trust language from that signal (not from wiki
   account policy).
3. Re-check the Sybil and credential-sharing mitigations against the new model.
