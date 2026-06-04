"""Minimal MediaWiki API client for verifying NB wiki credentials.

Pattern: GET a login token, POST action=login with the token + username +
password. Returns 'Success' or the failure reason string.

We never persist the password — it lives in memory for one HTTP roundtrip
to the wiki and is then discarded.
"""

from __future__ import annotations

import httpx

WIKI_API_URL = "https://www.noisebridge.net/api.php"
HTTP_TIMEOUT = 15.0


def verify_login(username: str, password: str) -> tuple[bool, str, str]:
    """Verify (username, password) against the NB wiki.

    Returns (ok, reason, canonical_username). On success, canonical_username is
    the wiki's normalized username (e.g. bot-password login "Nthmost@rubberducky"
    resolves to "Nthmost"). On failure it is empty.
    """
    if not username or not password:
        return False, "username and password required", ""
    with httpx.Client(timeout=HTTP_TIMEOUT, follow_redirects=True) as client:
        token = _fetch_login_token(client)
        return _attempt_login(client, username, password, token)


def _fetch_login_token(client: httpx.Client) -> str:
    """Step 1 of MediaWiki login: get a login-type CSRF token."""
    resp = client.get(WIKI_API_URL, params={
        "action": "query",
        "meta": "tokens",
        "type": "login",
        "format": "json",
    })
    resp.raise_for_status()
    return resp.json()["query"]["tokens"]["logintoken"]


def _attempt_login(
    client: httpx.Client, username: str, password: str, token: str,
) -> tuple[bool, str, str]:
    """Step 2: POST credentials. Returns (success, reason-or-empty, canonical_username)."""
    resp = client.post(WIKI_API_URL, data={
        "action": "login",
        "lgname": username,
        "lgpassword": password,
        "lgtoken": token,
        "format": "json",
    })
    resp.raise_for_status()
    body = resp.json().get("login", {})
    if body.get("result") == "Success":
        canonical = body.get("lgusername") or username
        return True, "", canonical
    reason = body.get("reason") or body.get("result") or "unknown"
    return False, reason, ""
