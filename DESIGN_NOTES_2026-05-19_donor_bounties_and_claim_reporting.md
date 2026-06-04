# Design Notes — Donor Bounties + Claim Reporting

**Date:** 2026-05-19
**Status:** Merged into SPEC.md 2026-05-19 (data model, mechanics, API surface, civic-hours certificate). This doc retained as the rationale / why-we-did-what record.
**Origin:** Discord thread — Project Forum › *NoiseQuest: Task Gamification + Catalogue System* — economics sub-discussion, 2026-05-19 ~17:51–19:13 UTC. Daniel (Web) proposed a donation-bounty mechanic; this doc captures the design that emerged from talking it through. The civic-hours layer (§8) was added later the same day after surfacing the in-progress SF City parking-ticket conversation.

---

## 1. What this adds to v1

Two new layers on top of the existing quest model:

1. **Donor bounties** — real-dollar gifts to NB, conditional on a quest being completed. The volunteer is never paid; the bounty goes to NB.
2. **Claim reporting** — per-claimer self-reported time, notes, photo, and done-state at claim-completion time.

Neither requires a redesign of the existing schema. Both attach cleanly to existing tables.

---

## 2. Donor bounties — the model

### What it is

A donor pledges $X to Noisebridge **conditional** on quest Y being completed. When a party claims and marks the quest done, NB collects the gift. The volunteer receives XP (existing mechanic), recognition, and the legible fact that their labor unlocked a real-dollar donation — but no cash flows to them.

### What it is *not*

- **Not a wage / not contractor pay.** No compensation flows to the doer. The volunteer remains a volunteer in every legal and tax sense.
- **Not free-market pricing.** Donor sets the dollar amount based on what they wish to express, not what labor "clears" at. No bidding, no competing claims on price.
- **Not escrow-style bounty pay-out.** Closest priors are: challenge grants ("matching" gift conditional on delivery), Kickstarter (pledge conditional on completion), bug bounties *inverted* (payout to org, not finder).

### Why this framing matters

- **Legally clean.** No 1099/employee/contractor question. Donor's gift is a standard 501(c)(3) restricted contribution, recognized on completion of the donor's stated condition.
- **Avoids the Gneezy/Rustichini trap.** Once volunteers are paid for civic behavior, intrinsic motivation collapses and the behavior degrades when payment stops. By directing the dollars to NB and the recognition to the doer, the system *augments* do-ocracy instead of crowding it out.
- **Produces two independently useful signals:**
  - **Demand signal** — bounty size = what donors actually value, in dollars.
  - **Capacity signal** — completion rate = what the community will show up for when prompted.

### What gets added to the schema

A new `quest_bounties` table (or `donor_pledges` — naming TBD):

| column | type | notes |
|---|---|---|
| id | bigint pk | |
| quest_id | fk quests.id | |
| donor_user_id | fk users.id nullable | nullable for anonymous |
| donor_display_name | text nullable | for anonymous-but-credited |
| amount_cents | int not null CHECK > 0 | dollar bounty in cents |
| pledged_at | timestamptz not null default now() | |
| collected_at | timestamptz nullable | set when quest reaches terminal state |
| expires_at | timestamptz nullable | optional sunset |
| stripe_payment_intent_id | text nullable | populated on collection |
| memo | text nullable | donor's stated reason / dedication |

Collection mechanics: **pledge-on-creation, charge-on-completion** is the simplest path — donor enters a payment method when pledging, NB captures on the `done` (or `verified`) transition. This avoids escrow and avoids the awkwardness of asking for money after the fact.

Stale-bounty handling (TBD; needs more thought):
- `expires_at` reached with quest still open → prompt donor: "convert pledge to unrestricted gift?" / "withdraw?" / "extend?"
- Pledge withdrawn → quest stays open, just loses the bounty marker
- This is a real conversion opportunity, not just a cleanup task

### Quest fields that reference bounties

Add to `quests` (or compute on read):
- `total_bounty_cents` (denormalized sum of active pledges, for sort/filter)
- `bounty_count` (denormalized, for "12 donors pledged" UI)

---

## 3. Claim reporting — the model

### What gets reported at claim-completion

Add to `quest_claims`:

| column | type | notes |
|---|---|---|
| time_spent_minutes | int nullable | self-reported, *per person*, not party-total |
| done_state | text nullable | `full` \| `partial` \| `blocked` — null until claim completes |
| claim_notes | text nullable | public, free-form, encouraged |
| photo_url | text nullable | optional |
| reported_at | timestamptz nullable | when this row was filled out |

Plus, for the photo system: a `quest_attachments` table is probably worth standing up properly (URL, mime type, uploaded_by, uploaded_at, scope = `'quest'` or `'claim'`). Stub it out now; even if photos go to the local filesystem in v1, having the row makes migration to object storage painless.

### What the claim form asks (UX, not API)

**Required:**
- Time spent (minutes), per person
- Done state: `full` / `partial` / `blocked`

**Optional but encouraged:**
- Notes ("what slowed me down" / "found this also broken" / "needs follow-up")
- Photo

**Hard constraint:** the form takes ≤ 60 seconds. Anything more and the data dries up.

### Design rules

These came out of the conversation and matter for keeping the data trustworthy:

1. **Time is for measurement, not competition.**
   - No speedrun bonuses.
   - No minimum-time thresholds.
   - No XP modifiers tied to reported duration.
   - The number exists to be aggregated, never to be optimized against.
2. **Per-person, not per-party.** If a party of 2 spent 18 min each, that's 36 person-minutes — useful for both per-person contribution history and aggregate volunteer-hour accounting. A single party-total field collapses both.
3. **Public by default.** Notes, time, photo all visible. Social verification is much cheaper than software verification (see §4).
4. **Don't gamify the data fields.** No badges for "fastest sweep" or "most photos uploaded." The contribution profile (§5) is reward enough.
5. **Bounties stay dollar-denominated, never abstracted.** Don't convert to "questbucks" or any internal currency. "$50 raised for NB" is the magic; "120 questbucks" is nothing.

---

## 4. Verification — what to require, what to punt

`requires_verification` already exists on `quests` and stays as-is. What changes is **the default disposition for most tasks**:

- **Default tier — self-attestation.** Party submits claim with time/notes/photo. Quest transitions to `done`. Bounty collected. No software adjudication of "is it really done?"
  - **The audit is social, after the fact.** If the hackitorium isn't actually swept tomorrow morning, the reputation system handles the long tail — not the claim flow.
  - Photo + notes + party + time being public is the verification mechanism. Software doesn't need to judge; the community does, asynchronously, by looking.
- **Co-sign tier** — for higher-stakes bounties or first-time adventurers, require a second party member or named witness to confirm. Schema already supports via `verifier_user_ids`.
- **Inspector tier** — quest creator (or named verifier) must confirm. Used rarely; reserved for genuinely high-stakes tasks where doing it badly is worse than not doing it.

Bounty creators (or quest creators) choose the tier at posting time. Most things are tier 1. The system should make tier 1 friction-free and tiers 2/3 slightly heavier — that's the right gradient.

### Why not stricter verification by default?

- 90% of tasks are low-stakes (sweep, restock, fix a flicker). Adjudicating each one in software is unnecessary overhead that suppresses participation.
- Public submissions create their own audit trail.
- Reputation builds slowly and naturally as a side-effect of consistent reporting, without anyone having to design a "reputation system."

---

## 5. What time-reporting unlocks (the real prize)

The claim-reporting layer is arguably bigger than the bounty mechanic itself. After 3–6 months of data:

1. **Calibrated bounty pricing.** Donors see "tasks tagged `sweep` average 18 min" before posting. Sets sane expectations.
2. **Operational cost transparency.** "Keeping NB clean costs ~40 volunteer-hours/week." Currently unknowable without something like this.
3. **Grant-writing gold.** [Independent Sector's "Value of Volunteer Time"](https://independentsector.org/value-of-volunteer-time/) is ~$33/hr nationally, $40+/hr in California (2024–25). Once you can write "*in Q3, adventurers contributed 612 hours valued at ~$24,500, plus $3,200 in donor bounties — total community-generated value of $27,700*," that paragraph slots straight into every grant application and every board update.
4. **Member-equity narrative.** "Your dues + your labor + bounties = the space exists." Makes the contribution stack visible and honest. Likely good for morale and member retention.
5. **Incident log as byproduct.** "Someone left nasty food in the corner" is a one-off comment; aggregate 6 months of those and you have an ethnography NB has never had. Recurring patterns surface; infrastructure interventions become evidence-backed.
6. **Contribution resume per adventurer.** "12 hrs volunteered, raised $340 for NB, completed: 8 sweeps, 2 laser-fixes, 1 inventory audit." Vastly more meaningful than "Level 7 Ranger" for membership consideration, board nominations, conflict-resolution standing, and the adventurer's own sense of belonging.

Reports/views to plan for (don't need to build in v1, but design data to support):
- Per-quest aggregate stats (median time, completion rate, party size distribution)
- Per-tag/category stats (cleaning vs. infrastructure vs. teaching)
- Per-adventurer contribution summary (the resume above)
- Org-wide rollups for board/grant reporting (hours × Independent Sector rate)
- Incident-log search across `claim_notes`

---

## 6. Open questions

- **Partial-claim flow.** If a party submits `done_state = partial`, does the quest stay open with a notation? Get re-priced (bounty stays, more work expected)? Or does the party just claim full credit with explanatory notes and the next attempt is a separate quest? Current intuition: stay open, surface the partial-claim history publicly, let community decide.
- **Bounty stacking.** Multiple donors pledge the same quest — sum them in UI? Cap at some amount? Cap per donor? (Probably: sum, no cap, but display top donors. Capping invites gaming.)
- **Anonymous donors.** Probably yes, with optional display name. Need a "memo" field they control vs. internal-only fields NB sees for receipt purposes.
- **Receipt generation.** 501(c)(3) acknowledgment letters at year-end. Out-of-scope for v1 but the schema should make it possible.
- **Bounty matching.** Could a donor pledge "I'll match the first $100 in bounties on quests tagged `accessibility` this month"? Probably v2.
- **Time-reporting calibration period.** First 1–2 months of data will be noisy. Plan to publish aggregate stats only after some threshold (e.g., 20 claims per task tag) to avoid misleading early "averages."

---

## 8. Civic-hours certificate (added later same day)

### The use case

Noisebridge has an in-progress conversation with the City of San Francisco about accepting volunteer hours at NB toward parking-ticket debt (and analogous civic obligations). The board is willing to sign off on hours. The Quest Board's per-claimer time data is the obvious substrate — *if* it can be turned into something the City will accept.

### The trust architecture (and why it's clean)

Self-attestation is fine for "did we sweep the hackitorium." It is **not** fine for "the City forgives this person $268 in parking tickets." That tension would normally demand a heavyweight verification layer: certifier accounts, ID-checking at certification time, real-name binding, an immutable `hour_certifications` table, signature workflows.

We need none of that, because Noisebridge already does the verification — **once, in person, at wiki-account creation**. An admin sits with the prospective member, vouches for them, and only then is the wiki account issued. That single fact makes wiki_username effectively 1:1 with a real human, even though we never store anything that looks like ID.

Every quest claim is bound to a wiki_username. Every wiki_username was vouched for face-to-face. The chain is intact.

This is *stronger* than most community-service programs the City already accepts. Food banks don't ID-check volunteers either; they just attest. NB attests too, and our attestation chain bottoms out in an in-person interaction.

### What the certificate looks like

A self-service endpoint (`GET /me/hours/certificate?from=…&to=…`) generates a printable document containing:

- NB letterhead + 501(c)(3) statement
- The user's wiki_username
- Optional user-supplied display name (asked at generation, not stored)
- Date range
- Total hours
- Per-quest breakdown
- The verbatim sentence:
  > *"Wiki accounts at Noisebridge are issued only after in-person verification by a Noisebridge administrator. The hours below were reported by [wiki_username], an account so verified."*
- Issue date
- Blank signature line for optional board countersignature (no system field; ink-on-paper)

### Design decisions

1. **No `certifier` role or scope.** The board explicitly chose to keep this anarchistic — no in-system designation of who can sign off. The certificate is system-issued under NB's institutional voice; a board member can add a wet signature only if the City asks for one.
2. **No real-name binding stored.** The user writes their legal name on the document at generation time (the optional `display_name` query param), or in pen, or not at all. NB doesn't keep a wiki_username ↔ legal name map.
3. **No `hour_certifications` table.** The certificate is derived on-demand from `quest_claims.time_spent_minutes`. There's no separate immutable record because the claim ledger itself is the record.
4. **No promotion workflow.** No "request certification" → "approve" loop. Every claim is potentially certifiable just by being a claim by a verified wiki user.
5. **Admin generation on behalf of a user** is supported (`GET /users/{id}/hours/certificate`) for board members printing certificates at the space for users without a device handy.
6. **Sybil mitigation is the wiki-account policy, not the Quest Board.** If wiki signup ever becomes self-serve, the entire civic-hours story collapses and the certificate language must change. This dependency is documented in SPEC §1 design principles on purpose.

### What gets flagged but explicitly accepted

These were raised in the design conversation and the user/board chose to accept the residual risk:

- **Credential sharing.** A wiki account holder hands creds to a friend who claims hours under that account. Same risk profile as any password sharing; not a Quest Board problem to solve. Board declines to sign if patterns become egregious.
- **City may eventually want more.** If the City asks for stronger assurance later, the easiest add is a board-countersigned variant of the certificate. The data model doesn't have to change; only the document template gains a required signature field.
- **No pre-emptive flags on implausible totals.** No "1000 hours in a month" auto-flag. If a number looks wrong, the board notices when asked to countersign and addresses it human-to-human. The system's job is accurate accounting, not adjudication.

### What this combines with, downstream

The civic-hours use case **strengthens the case for the entire time-reporting layer**. Even members who never need a parking-ticket certificate benefit, because:

- The same per-person data feeds the contribution resume (§5)
- The same data feeds operational-hours grant-writing totals (§5)
- The same data calibrates donor-bounty pricing (§5)
- The same data produces the civic-hours certificate (this section)

Four downstream uses, one substrate. That's the leverage.

---

## 9. What does *not* belong in this design

For the record, so they don't creep in later:

- **Cash payouts to volunteers** — the entire premise rejects this.
- **Auction / bidding for tasks** — donors set bounties, doers don't compete on price.
- **Speedrun bonuses, time-based leaderboards, fastest-claim badges** — corrupts the measurement data.
- **Internal currency (questbucks, etc.) standing in for real dollars on the bounty side** — kills both the demand signal and the grant-writing utility.
- **Mandatory verification for all tasks** — software-adjudicated verification at scale suppresses participation; the social/reputation layer does the heavy lifting.
- **Certifier accounts / certifier scope for civic hours** — the board explicitly chose not to introduce in-system "authorized signatory" roles. Trust is institutional, not individual-account-level.
- **Real-name binding stored alongside wiki_username** — no `user_legal_identity` table, no encrypted PII at rest. The user writes their name on the printed certificate at use time.
- **Auto-flagging implausible hour totals** — handled by humans noticing, not by software thresholds.
