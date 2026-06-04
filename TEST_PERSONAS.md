# NoiseQuest Test Personas

Working list for scenario / user-journey testing. Personas are grouped by the axis they sit on; many real users combine multiple axes (e.g. "new member who wants civic hours" crosses A + B).

Edit freely. Add, remove, merge, rename. Adjust the tier assignments at the bottom as priorities shift.

---

## A. Tenure axis — how long they've been at NB

1. **First-time visitor** — walked in for the first time, no wiki account yet, doesn't know what NB is
2. **New wiki member** — just got their account approved by an admin, hasn't done anything yet
3. **Active regular** — months in, knows the rhythms, has a few completed quests
4. **Old guard** — years in, may be quest-board-skeptical, has strong opinions about how things should work
5. **Returning lapsed** — was active, drifted away, coming back to find things changed

## B. Motivation axis — why they're touching the quest board

6. **Builder/maker** — here for projects, sees chores as background noise; quests are barely on their radar
7. **Do-ocrat/steward** — already does the chores; quest board formalizes what they were doing anyway
8. **Gamer/quester** — actively enjoys the XP/level loop, optimizes for completion velocity
9. **Mentor** — runs classes, wants to post Guild-promotion quests for apprentices
10. **Apprentice/learner** — working a Campaign toward Guild membership
11. **Hours-for-tickets seeker** — primarily here for the civic-hours certificate; the rest is incidental
12. **Court-ordered community service** — like above but with a court-defined hour requirement and a real deadline
13. **Resume-builder** — wants documented volunteer hours for a job/school application
14. **Donor-bounty poster** — never claims a quest, only funds them

## C. Role axis — institutional position

15. **Associate (non-paying member)** — has wiki, no dues
16. **Dues-paying member**
17. **Guild lead** — moderates a Guild, approves Campaign progress
18. **Board member** — countersigns civic-hours certs, sees aggregate financials
19. **Admin** — full system access, handles disputes
20. **Quartermaster (NPC in demo)** — system-voice poster; in the real version, a human in that role

## D. Channel / accessibility axis — how they actually touch the system

21. **In-space-only user** — uses NB terminals, doesn't bring a device, depends on space-based access
22. **Mobile-only user** — phone is their only computer, never sees the desktop UI
23. **Screen-reader user** — accessibility is binary, the UI works or it doesn't
24. **Non-English-primary speaker** — UI text, quest descriptions, certificate wording all need to scan
25. **Limited-time user** — parent, shift worker, has 90-min windows; needs quests that fit
26. **Discord-only person** — never visits the space, active in chat — does the quest board even apply?

## E. External system axis — non-human consumers

27. **BBS (MOOdBBS) feed reader** — polls public endpoints for display
28. **Home Assistant @ NB** — displays current quest board / leaderboard on space dashboards
29. **Wiki user-page badge fetcher** — server-rendered SVG cache (future)
30. **Scraper / archivist** — third-party tool consuming public API
31. **LLM assist agent** — internal, drafts quests for human review

## F. Adversarial / edge axis — the personas that break things

32. **Hoarder** — claims many quests, completes few, holds quest capacity hostage
33. **Drive-by** — picks the easiest quests, never blocked tasks, optimizes XP/effort ratio
34. **Disputant** — argues that other people's claims weren't really "done"
35. **The 86'd-then-back** — has past trust history with NB, may be re-entering carefully
36. **Credential-sharer** — gives wiki creds to a friend; claims show under one account
37. **The implausible-hours person** — racks up suspicious hours, triggers human review
38. **Bounty-and-claim collusion** — donor pledges a quest, friend claims it; NB gets the money but the social audit looks weird

## G. Identity-edge axis — where the wiki-verified personhood model gets stressed

39. **Person whose wiki name doesn't match their preferred name** — esp. for civic-hours certs
40. **Person who was verified once but now uses a different identity** — name changes, transitions, etc.
41. **Anonymous donor** — pledges money but doesn't want their name attached anywhere
42. **Anonymous-but-credited donor** — wants memorial/dedication credit, no real name

---

## Ranking heuristics

Suggested criteria for prioritizing which personas to build scenarios for first:

- **Coverage value** — building tests for this persona exercises the most distinct code paths
- **Volume** — how many real users match this persona at any given time
- **Stake** — how badly things go if this persona has a broken experience (civic-hours seeker > drive-by gamer)
- **Risk surface** — does this persona's misuse threaten data integrity, fairness, or NB's institutional reputation
- **Recency / novelty** — do we have *any* observational data on this persona, or is everything we'd test pure assumption

Rough rule of thumb: **stake × volume**, with **risk surface** as a tiebreaker that pulls adversarial personas up the list earlier than their volume alone would justify.

---

## Starter tier cut (gut feel, pre-discussion)

### Tier 1 — must work, day 1
- #2 New wiki member
- #3 Active regular
- #7 Do-ocrat/steward
- #11 Hours-for-tickets seeker
- #14 Donor-bounty poster
- #19 Admin

### Tier 2 — must work, week 1
- #9 Mentor
- #10 Apprentice/learner
- #17 Guild lead
- #18 Board member
- #27 BBS feed reader
- #28 Home Assistant @ NB
- #32 Hoarder

### Tier 3 — test before public launch
- #4 Old guard skeptic
- #22 Mobile-only user
- #25 Limited-time user
- #36 Credential-sharer
- #37 Implausible-hours person

### Tier 4 — later
- #12 Court-ordered community service
- #13 Resume-builder
- #23 Screen-reader user
- #24 Non-English-primary speaker
- #31 LLM assist agent
- #41 Anonymous donor
- #42 Anonymous-but-credited donor

### Probably out of scope for testing
- #1 First-time visitor (pre-wiki account; not yet a user of the system)
- #26 Discord-only person (doesn't actually touch the Quest Board)

---

## Open questions / notes for next pass

- Are there persona crosses we should treat as their own first-class persona? (e.g. "civic-hours seeker who is also new to the space" is probably distinct enough from #11 alone to warrant its own scenario set)
- Do board members / admins need separate read-only vs write-permission personas for testing?
- Should the NPC Quartermaster (#20) be tested as a *persona* or as part of the demo simulation harness?
- Is there an "ex-member" or "asked-to-leave" persona that needs handling? (different from #35; this is someone who shouldn't have access at all)
