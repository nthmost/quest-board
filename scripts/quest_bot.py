#!/usr/bin/env python3
"""
quest_bot.py — Progress Quest-style automated tester for the quest-board API.

Logs in, creates a character, and cycles: browse → claim → hold → release.
Exercises every live API endpoint on each tick and narrates the adventure.

Configuration via environment:
    NBQUEST_URL          base URL (default: http://localhost:8000)
    NBQUEST_WIKI_USER    wiki login name
    NBQUEST_WIKI_PASS    wiki password (or bot password)
    NBQUEST_CHAR_NAME    character display name (default: RubberDucky)
    NBQUEST_CHAR_CLASS   character class slug  (default: hacker)
    NBQUEST_HOLD_SECS    seconds to hold a claimed quest (default: 120)
    NBQUEST_TICK_SECS    seconds between ticks (default: 30)
"""

from __future__ import annotations

import argparse
import json
import os
import random
import re
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

import httpx

# ---------------------------------------------------------------------------
# Defaults
# ---------------------------------------------------------------------------

BASE_URL = "http://localhost:8000"
DEFAULT_CHAR_NAME = "RubberDucky"
DEFAULT_CHAR_CLASS = "hacker"
DEFAULT_HOLD = 120
DEFAULT_TICK = 30
MAX_HELD = 2
STATE_PATH = Path("~/.nbquest/quest_bot_state.json").expanduser()

# ---------------------------------------------------------------------------
# Progress Quest flavor text
# ---------------------------------------------------------------------------

CLAIM_FLAVOR = [
    "cracks knuckles and steps forward",
    "was just about to do that anyway",
    "has done this before. Will do it again.",
    "checks the list twice, then claims without hesitation",
    "nods gravely and steps up to the board",
    "shouts 'I got this!' across the space",
    "is seen gathering relevant supplies",
]

HOLD_FLAVOR = [
    "is somewhere in the building",
    "sent a thumbs-up and went quiet",
    "was spotted near the relevant equipment",
    "is asking clarifying questions to no one in particular",
    "appears to be making progress",
    "has not returned yet, but the screwdriver is missing",
]

RELEASE_FLAVOR = [
    "has to catch a BART",
    "yields the floor gracefully",
    "steps back to let others shine",
    "logs a partial and departs",
    "returns the ticket to the queue",
    "gracefully un-claims and disappears",
]


DONE_FLAVOR = [
    "steps back and surveys their handiwork",
    "announces completion with unearned confidence",
    "marks it done and reaches for the XP",
    "submits the ticket and hopes no one checks",
    "high-fives nobody in particular",
    "files it under W and walks away",
]

# ---------------------------------------------------------------------------
# State helpers
# ---------------------------------------------------------------------------

def load_state() -> dict:
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    if STATE_PATH.exists():
        try:
            return json.loads(STATE_PATH.read_text())
        except (json.JSONDecodeError, OSError):
            pass
    return {
        "active_claims": [],
        "claims_total": 0,
        "ticks_total": 0,
        "started_at": datetime.now(UTC).isoformat(),
        "character_id": None,
        "character_name": None,
        "character_class": None,
    }


def save_state(state: dict) -> None:
    STATE_PATH.write_text(json.dumps(state, indent=2))


# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

def log(section: str, msg: str, ok: bool = True) -> None:
    ts = datetime.now(UTC).strftime("%H:%M:%S")
    mark = "✓" if ok else "✗"
    label = section.upper().ljust(12)
    print(f"  [{ts}] {mark} {label}  {msg}")


def die(msg: str) -> None:
    print(f"\nFATAL: {msg}", file=sys.stderr)
    sys.exit(1)


# ---------------------------------------------------------------------------
# Credential loading
# ---------------------------------------------------------------------------

def load_credentials() -> tuple[str, str]:
    """Return (wiki_user, wiki_pass) from env or ~/.secrets/nbwiki.env."""
    user = os.environ.get("NBQUEST_WIKI_USER") or os.environ.get("NOISEBRIDGE_WIKI_USER")
    pw = os.environ.get("NBQUEST_WIKI_PASS") or os.environ.get("NOISEBRIDGE_WIKI_PASSWORD")
    if user and pw:
        return user, pw

    secrets = Path("~/.secrets/nbwiki.env").expanduser()
    if secrets.exists():
        for line in secrets.read_text().splitlines():
            if "=" in line and not line.startswith("#"):
                k, v = line.split("=", 1)
                k, v = k.strip(), v.strip()
                if k == "NOISEBRIDGE_WIKI_USER":
                    user = v
                elif k == "NOISEBRIDGE_WIKI_PASSWORD":
                    pw = v

    if user and pw:
        return user, pw
    die(
        "No wiki credentials found.\n"
        "Set NBQUEST_WIKI_USER + NBQUEST_WIKI_PASS, "
        "or put them in ~/.secrets/nbwiki.env."
    )
    return "", ""  # unreachable


# ---------------------------------------------------------------------------
# QuestBot
# ---------------------------------------------------------------------------

class QuestBot:
    def __init__(
        self,
        base_url: str,
        wiki_user: str,
        wiki_pass: str,
        char_name: str,
        char_class: str,
        hold_secs: int,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.wiki_user = wiki_user
        self.wiki_pass = wiki_pass
        self.char_name = char_name
        self.char_class = char_class
        self.hold_secs = hold_secs
        self.client = httpx.Client(
            base_url=self.base_url,
            follow_redirects=True,
            timeout=20.0,
        )
        self.state = load_state()
        self._tick_n = 0
        self._guild_cache: list[dict] = []

    # ------------------------------------------------------------------
    # Session lifecycle
    # ------------------------------------------------------------------

    def login(self) -> None:
        r = self.client.post("/login", data={
            "username": self.wiki_user,
            "password": self.wiki_pass,
        })
        if "/login" in str(r.url):
            die(f"Login failed for {self.wiki_user!r} — check wiki credentials")
        log("auth", f"Logged in as {self.wiki_user}")

    def ensure_character(self) -> None:
        """Create the bot's character if absent; confirm it's active."""
        r = self.client.get("/me/characters")
        if r.status_code != 200:
            die(f"/me/characters returned {r.status_code}")
        html = r.text

        if self.char_name in html:
            # Character exists — extract id from first activate/delete form
            char_id = self._parse_first_char_id(html)
            if char_id and char_id != self.state.get("character_id"):
                self.state["character_id"] = char_id
            log("character", f"Found '{self.char_name}' (id={self.state.get('character_id')})")
            self._ensure_active()
        else:
            log("character", f"Creating '{self.char_name}' ({self.char_class})...")
            r = self.client.post("/me/characters", data={
                "name": self.char_name,
                "class_slug": self.char_class,
                "primary_guild_id": "",
            })
            if r.status_code not in (200, 303) or "/me/characters" not in str(r.url):
                die(f"Character creation failed (status {r.status_code}, url {r.url})")
            # Re-fetch to get id
            r2 = self.client.get("/me/characters")
            char_id = self._parse_first_char_id(r2.text)
            self.state["character_id"] = char_id
            log("character", f"'{self.char_name}' created! +100 XP welcome grant. (id={char_id})")

        self.state["character_name"] = self.char_name
        self.state["character_class"] = self.char_class
        save_state(self.state)

    def _parse_first_char_id(self, html: str) -> int | None:
        """Extract first character id from /me/characters HTML."""
        m = re.search(r'action="/me/characters/(\d+)/', html)
        return int(m.group(1)) if m else None

    def _ensure_active(self) -> None:
        """If we have a stored character_id, activate it."""
        char_id = self.state.get("character_id")
        if not char_id:
            return
        r = self.client.post(f"/me/characters/{char_id}/activate")
        # Redirects to /me/characters on success or if already active
        if "/me/characters" in str(r.url):
            log("character", f"Character {char_id} is active")

    # ------------------------------------------------------------------
    # Main tick
    # ------------------------------------------------------------------

    def tick(self) -> None:
        self._tick_n += 1
        ts = datetime.now(UTC).strftime("%H:%M:%S")
        char_name = self.state.get("character_name", "???")
        claims_n = len(self.state.get("active_claims", []))
        total = self.state.get("claims_total", 0)

        print(f"\n{'─' * 62}")
        print(f"  [{ts}] TICK #{self._tick_n}  "
              f"★ {char_name} the {self.char_class.title()}  "
              f"claims held={claims_n}  total={total}")
        print(f"{'─' * 62}")

        # Meta endpoints — every tick
        self._api_healthz()
        self._api_version()
        self._api_stats()
        self._api_economy()

        # Taxonomy — every 5 ticks
        if self._tick_n % 5 == 1:
            self._guild_cache = self._api_guilds()
            self._api_locations()

        # Release claims that have been held long enough
        self._release_old_claims()

        # Browse quests with a rotating filter for endpoint coverage
        quests = self._api_quests_browse()

        # Inspect a random quest detail
        open_quests = [q for q in quests if q.get("status") == "open"]
        if quests:
            target = random.choice(quests[:15])
            self._api_quest_detail(target["id"])

        # Claim if below capacity
        if claims_n < MAX_HELD and open_quests:
            self._try_claim(open_quests)

        self.state["last_tick"] = datetime.now(UTC).isoformat()
        self.state["ticks_total"] = self.state.get("ticks_total", 0) + 1
        save_state(self.state)

    # ------------------------------------------------------------------
    # API exercisers (JSON endpoints)
    # ------------------------------------------------------------------

    def _api_healthz(self) -> bool:
        r = self.client.get("/api/v1/healthz")
        ok = r.status_code == 200
        log("healthz", "OK" if ok else f"FAIL ({r.status_code})", ok)
        return ok

    def _api_version(self) -> None:
        r = self.client.get("/api/v1/version")
        if r.status_code == 200:
            log("version", f"v{r.json().get('version', '?')}")

    def _api_stats(self) -> None:
        r = self.client.get("/api/v1/stats")
        if r.status_code != 200:
            log("stats", f"FAIL ({r.status_code})", False)
            return
        s = r.json()
        log("stats", (
            f"quests={s.get('quest_count')}  "
            f"open={s.get('quests_open')}  "
            f"done={s.get('quests_done')}  "
            f"users={s.get('user_count')}  "
            f"XP minted={s.get('total_xp_minted')}"
        ))

    def _api_economy(self) -> None:
        r = self.client.get("/api/v1/economy")
        if r.status_code != 200:
            log("economy", f"FAIL ({r.status_code})", False)
            return
        cfg = r.json().get("config", {})
        xp = cfg.get("xp", {})
        grant = xp.get("welcome_grant", {}).get("amount", "?")
        fee = xp.get("posting_fee", {}).get("flat_amount", "?")
        log("economy", f"welcome_grant={grant} XP  posting_fee={fee} XP")

    def _api_guilds(self) -> list[dict]:
        r = self.client.get("/api/v1/guilds")
        if r.status_code != 200:
            log("guilds", f"FAIL ({r.status_code})", False)
            return []
        guilds = r.json()
        preview = ", ".join(g["slug"] for g in guilds[:5])
        log("guilds", f"{len(guilds)} guilds: {preview}...")
        return guilds

    def _api_locations(self) -> list[dict]:
        r = self.client.get("/api/v1/locations")
        if r.status_code != 200:
            log("locations", f"FAIL ({r.status_code})", False)
            return []
        locs = r.json()
        preview = ", ".join(l["slug"] for l in locs[:5])
        log("locations", f"{len(locs)} locations: {preview}...")
        return locs

    def _api_quests_browse(self) -> list[dict]:
        """Rotate through different filter combinations for endpoint coverage."""
        params: dict = {"limit": 20}
        variant = self._tick_n % 6
        if variant == 0:
            params["status"] = "open"
        elif variant == 1:
            pass  # no filter
        elif variant == 2:
            params["status"] = "open"
            if self._guild_cache:
                params["guild_id"] = random.choice(self._guild_cache)["id"]
        elif variant == 3:
            params["status"] = "claimed"
        elif variant == 4:
            params["status"] = "open"
            params["limit"] = 5  # small page
        else:
            params["status"] = "open"
            params["limit"] = 50  # large page

        r = self.client.get("/api/v1/quests", params=params)
        if r.status_code != 200:
            log("quests", f"FAIL ({r.status_code})", False)
            return []
        data = r.json()
        items = data.get("items", [])
        filter_desc = " ".join(f"{k}={v}" for k, v in params.items())
        log("quests", f"{len(items)} returned  [{filter_desc}]")
        return items

    def _api_quest_detail(self, quest_id: int) -> dict | None:
        r = self.client.get(f"/api/v1/quests/{quest_id}")
        if r.status_code != 200:
            log("quest_detail", f"#{quest_id} FAIL ({r.status_code})", False)
            return None
        q = r.json()
        title = q.get("title", "?")[:48]
        xp = q.get("xp", "?")
        status = q.get("status", "?")
        skills = ", ".join(q.get("skills") or [])[:30]
        log("quest_detail", f"#{quest_id} [{status}] '{title}' — {xp} XP  [{skills}]")
        return q

    # ------------------------------------------------------------------
    # Claim / release (session-based form endpoints)
    # ------------------------------------------------------------------

    def _try_claim(self, open_quests: list[dict]) -> None:
        # Avoid re-claiming quests we already hold
        held_ids = {c["quest_id"] for c in self.state.get("active_claims", [])}
        eligible = [q for q in open_quests if q["id"] not in held_ids]
        if not eligible:
            log("claim", "No eligible open quests to claim this tick")
            return

        quest = random.choice(eligible[:15])
        quest_id = quest["id"]
        title = quest.get("title", "?")[:45]

        r = self.client.post(f"/quests/{quest_id}/claim")
        final = str(r.url)

        if "/login" in final:
            log("claim", f"#{quest_id} — session expired, re-login needed", False)
            return
        if "flash=" in final:
            log("claim", f"#{quest_id} '{title}' — server rejected claim", False)
            return

        flavor = random.choice(CLAIM_FLAVOR)
        log("claim", f"#{quest_id} '{title}'  +claim  {self.char_name} {flavor}")
        self.state.setdefault("active_claims", []).append({
            "quest_id": quest_id,
            "title": title,
            "claimed_at": datetime.now(UTC).isoformat(),
        })
        self.state["claims_total"] = self.state.get("claims_total", 0) + 1

    def _release_old_claims(self) -> None:
        now = datetime.now(UTC)
        still_held = []
        for claim in self.state.get("active_claims", []):
            claimed_at = datetime.fromisoformat(claim["claimed_at"])
            age = (now - claimed_at).total_seconds()
            if age >= self.hold_secs:
                if not self._do_done(claim):
                    self._do_release(claim)
            else:
                remaining = int(self.hold_secs - age)
                flavor = random.choice(HOLD_FLAVOR)
                log("hold", (
                    f"#{claim['quest_id']} '{claim['title'][:38]}'  "
                    f"{flavor}  ({remaining}s left)"
                ))
                still_held.append(claim)
        self.state["active_claims"] = still_held

    def _do_done(self, claim: dict) -> bool:
        """Mark a held quest done (earns XP). Returns True on success."""
        quest_id = claim["quest_id"]
        title = claim.get("title", "?")[:45]
        r = self.client.post(
            f"/quests/{quest_id}/done",
            data={"claim_notes": "", "time_spent_minutes": ""},
        )
        final = str(r.url)
        ok = "/login" not in final and "flash=" not in final and r.status_code in (200, 303)
        flavor = random.choice(DONE_FLAVOR)
        label = "[done ★ XP earned]" if ok else "FAIL — falling back to release"
        log("done", f"#{quest_id} '{title}'  {label}  {self.char_name} {flavor}", ok)
        return ok

    def _do_release(self, claim: dict) -> None:
        """Release a held quest (no XP). Used as fallback if /done fails."""
        quest_id = claim["quest_id"]
        title = claim.get("title", "?")[:45]
        r = self.client.post(f"/quests/{quest_id}/release")
        final = str(r.url)
        ok = "/login" not in final and r.status_code in (200, 303)
        flavor = random.choice(RELEASE_FLAVOR)
        label = "[released]" if ok else "FAIL"
        log("release", f"#{quest_id} '{title}'  {label}  {self.char_name} {flavor}", ok)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def _print_banner(char_name: str, char_class: str, base_url: str) -> None:
    print()
    print("=" * 62)
    print("  N B Q U E S T   B O T")
    print(f"  {char_name} the {char_class.title()}")
    print(f"  Progress Quest-style API tester")
    print(f"  Target: {base_url}")
    print("=" * 62)


def main() -> None:
    ap = argparse.ArgumentParser(
        description="Automated quest user — exercises all quest-board API endpoints"
    )
    ap.add_argument("--url", default=os.environ.get("NBQUEST_URL", BASE_URL))
    ap.add_argument("--once", action="store_true", help="Run one tick and exit")
    ap.add_argument(
        "--interval",
        type=int,
        default=int(os.environ.get("NBQUEST_TICK_SECS", DEFAULT_TICK)),
        metavar="SECS",
        help=f"Seconds between ticks (default: {DEFAULT_TICK})",
    )
    ap.add_argument(
        "--hold",
        type=int,
        default=int(os.environ.get("NBQUEST_HOLD_SECS", DEFAULT_HOLD)),
        metavar="SECS",
        help=f"Seconds to hold a claimed quest before releasing (default: {DEFAULT_HOLD})",
    )
    ap.add_argument("--char-name", default=os.environ.get("NBQUEST_CHAR_NAME", DEFAULT_CHAR_NAME))
    ap.add_argument("--char-class", default=os.environ.get("NBQUEST_CHAR_CLASS", DEFAULT_CHAR_CLASS))
    args = ap.parse_args()

    wiki_user, wiki_pass = load_credentials()
    _print_banner(args.char_name, args.char_class, args.url)

    bot = QuestBot(
        base_url=args.url,
        wiki_user=wiki_user,
        wiki_pass=wiki_pass,
        char_name=args.char_name,
        char_class=args.char_class,
        hold_secs=args.hold,
    )

    bot.login()
    bot.ensure_character()

    if args.once:
        bot.tick()
        return

    try:
        while True:
            bot.tick()
            time.sleep(args.interval)
    except KeyboardInterrupt:
        print(f"\n\n  {args.char_name} sheathes their tools and departs.")
        print(f"  State saved to {STATE_PATH}")
        print()


if __name__ == "__main__":
    main()
