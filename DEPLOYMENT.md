# Quest Board — Deployment Runbook

> **Orientation:** Ops runbook for the live service. The design lives in
> [SPEC.md](./SPEC.md) and [DEMO.md](./DEMO.md); this file is *how to put
> it on the box*. For current operational state, see [STATUS.md](./STATUS.md).
> If you're brand new, start with [README.md](./README.md).

## Two deployments — read this first

As of 2026-05-09 the **demo** (`nbprogressquest.nthmost.net`) and the future
**real Noisebridge quest/task board** (planned for enki) are
deliberately separate deployments with separate databases. Don't merge
them.

- **Demo — live now.** Runs on a Debian host (Postgres 18, Python
  3.13). Service: `questboard.service`. Apache reverse-proxies the
  public hostname to `127.0.0.1:8080`. This is the canonical demo of
  the design.
- **Enki — quiesced, reserved for future work.** The original
  demo deployment (Ubuntu 24.04, Postgres 16) has been stopped and
  disabled. DB and code are preserved on disk but no longer serve
  traffic. When the NB community settles on what the real task board
  should look like, enki gets a fresh database (and likely a
  fresh hostname — `quests.noisebridge.net`). The sections below
  document the original enki-style deployment and remain useful
  as the template for that future setup, but **do not run them
  against the enki box again without fresh planning** — the
  spec for the real board hasn't been written yet.

Operational steps to bring up the quest board API on **enki** at Noisebridge.

Companion to [SPEC.md](./SPEC.md). The spec defines *what* the system does; this file defines *how to put it on the box*.

---

## Target environment

| Property | Value |
|---|---|
| Host | enki (NB) |
| OS | Ubuntu 24.04 |
| CPU / RAM | Intel i5-14450HX, 31 GB |
| GPU | Intel UHD iGPU (Ollama runs CPU-only) |
| Disk | 938 GB NVMe (~750 GB free) |
| SSH | via the operator's ssh config (host alias) |

Public hostname (interim): **`nbquests.nthmost.net`**. Migration to `quests.noisebridge.net` requires a callback re-registration with the wiki OAuth consumer (see §3 below).

---

## 1. System prerequisites

Already in place:

- [x] Ollama installed (`/usr/local/bin/ollama`, systemd service active)
- [x] Models pulled: `qwen2.5:7b`, `llama3.2:3b`
- [x] nginx installed (currently serving the now-empty `maxheadroom` site; consider disabling)

Still to install:

- [ ] PostgreSQL 16+ — `apt install postgresql`
- [ ] Python 3.12 (Ubuntu 24.04 ships with 3.12) + `python3-venv`
- [ ] `certbot` + `python3-certbot-nginx` for Let's Encrypt
- [ ] `argon2-cffi` (via pip into the app venv) for API-key hashing

---

## 2. Service user and filesystem layout

```
/opt/questboard/                 # app code (cloned from git)
/opt/questboard/.venv/           # Python virtualenv
/etc/questboard/economy.yaml     # the source-of-truth economy config
/var/log/questboard/             # app logs (also goes to journald)
/home/questboard/.secrets/       # secrets (mode 600, owned by service user)
```

Service user: `questboard` (system user, no shell login).

```bash
sudo useradd --system --home /home/questboard --shell /usr/sbin/nologin questboard
sudo mkdir -p /opt/questboard /etc/questboard /var/log/questboard /home/questboard/.secrets
sudo chown -R questboard:questboard /opt/questboard /var/log/questboard /home/questboard
sudo chown root:questboard /etc/questboard && sudo chmod 750 /etc/questboard
```

---

## 3. MediaWiki OAuth consumer registration

You have admin on the NB wiki. Steps:

1. **Install the OAuth extension** on the wiki if not already present (`mw:Extension:OAuth`). Add to `LocalSettings.php`:
   ```php
   wfLoadExtension( 'OAuth' );
   $wgMWOAuthCentralWiki = false;  // single-wiki setup
   ```
2. **Register the consumer** at `Special:OAuthConsumerRegistration/propose`:
   - Application name: `Noisebridge Quest Board`
   - Description: `Quest board API integration — reads username for identity.`
   - Callback URL: `https://nbquests.nthmost.net/api/v1/auth/wiki/callback`
   - Allow consumer to specify a callback prefix: **No** (exact match).
   - Applicable project: NB wiki only.
   - Grants needed: `basic` (just username + user ID).
3. **Self-approve** as wiki admin via `Special:OAuthManageConsumers`.
4. Capture the **consumer key** and **consumer secret**. Place in `/home/questboard/.secrets/wiki-oauth.env`:
   ```
   WIKI_OAUTH_CONSUMER_KEY=...
   WIKI_OAUTH_CONSUMER_SECRET=...
   WIKI_OAUTH_AUTHORIZE_URL=https://wiki.noisebridge.net/wiki/Special:OAuth/authorize
   WIKI_OAUTH_TOKEN_URL=https://wiki.noisebridge.net/w/index.php?title=Special:OAuth/token
   WIKI_OAUTH_IDENTIFY_URL=https://wiki.noisebridge.net/w/index.php?title=Special:OAuth/identify
   ```
5. `chmod 600` and `chown questboard:questboard` the file.

**Hostname migration note.** When we move to `quests.noisebridge.net`, the callback URL changes. Either re-register the consumer (preferred) or, if the OAuth extension allows, update the callback on the existing consumer record. Plan for ~24 hours of double-callback availability if possible.

---

## 4. PostgreSQL setup

```bash
sudo -u postgres createuser --pwprompt questboard
sudo -u postgres createdb --owner=questboard questboard
```

DB password goes in `/home/questboard/.secrets/db.env`:
```
DATABASE_URL=postgresql+psycopg://questboard:<password>@127.0.0.1:5432/questboard
```

Tune `pg_hba.conf` to allow `local` and `127.0.0.1/32` for `questboard` only.

Backups: nightly `pg_dump` cron entry on enki rsync'd to zephyr (see §8).

---

## 5. Economy YAML

Initial `/etc/questboard/economy.yaml` template lives in the repo at `quest-board/economy.example.yaml` (TODO: create alongside the app). On first deploy:

```bash
sudo cp /opt/questboard/economy.example.yaml /etc/questboard/economy.yaml
sudo chown root:questboard /etc/questboard/economy.yaml
sudo chmod 640 /etc/questboard/economy.yaml
```

After editing the YAML, hot-reload without restart:
```bash
sudo systemctl kill -s HUP questboard.service
```

The app re-validates the config on SIGHUP and rejects invalid changes (logs the error and keeps the previous config in memory).

---

## 6. systemd unit

`/etc/systemd/system/questboard.service`:

```ini
[Unit]
Description=Noisebridge Quest Board API
After=network.target postgresql.service ollama.service

[Service]
Type=notify
User=questboard
Group=questboard
WorkingDirectory=/opt/questboard
EnvironmentFile=/home/questboard/.secrets/db.env
EnvironmentFile=/home/questboard/.secrets/wiki-oauth.env
ExecStart=/opt/questboard/.venv/bin/uvicorn app.main:app \
    --host 127.0.0.1 --port 8080 --workers 2
Restart=on-failure
RestartSec=5
KillSignal=SIGTERM
TimeoutStopSec=20
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
```

Enable + start:
```bash
sudo systemctl daemon-reload
sudo systemctl enable --now questboard.service
```

---

## 7. nginx + TLS

`/etc/nginx/sites-available/questboard`:

```nginx
server {
    listen 80;
    server_name nbquests.nthmost.net;
    return 301 https://$host$request_uri;
}

server {
    listen 443 ssl http2;
    server_name nbquests.nthmost.net;

    # Cert managed by certbot:
    ssl_certificate     /etc/letsencrypt/live/nbquests.nthmost.net/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/nbquests.nthmost.net/privkey.pem;

    # Cache the public badge endpoints aggressively (future v1.x).
    location ~ ^/api/v1/users/by-wiki/[^/]+/badge {
        proxy_pass http://127.0.0.1:8080;
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-For $remote_addr;
        proxy_cache_valid 200 5m;
    }

    location / {
        proxy_pass http://127.0.0.1:8080;
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-For $remote_addr;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    client_max_body_size 1M;
}
```

DNS: add an A record for your chosen public hostname pointing at the deploy host's public IP.

TLS:
```bash
sudo a2dissite maxheadroom    # cleaning up the dead intake-era site
sudo ln -s /etc/nginx/sites-available/questboard /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl reload nginx
sudo certbot --nginx -d nbquests.nthmost.net
```

(If `a2dissite` doesn't exist on this Ubuntu, just `sudo rm /etc/nginx/sites-enabled/maxheadroom`.)

---

## 8. Backups

Cron on enki (`crontab -e` as `questboard`):

```cron
30 3 * * * /opt/questboard/scripts/backup.sh
```

`/opt/questboard/scripts/backup.sh`:
```bash
#!/usr/bin/env bash
set -euo pipefail
DATE=$(date +%Y%m%d)
DUMP="/var/backups/questboard/questboard-${DATE}.sql.gz"
mkdir -p /var/backups/questboard
pg_dump questboard | gzip > "$DUMP"
# Push to zephyr; keep 30 days local, indefinite remote.
rsync -a "$DUMP" zephyr:/var/backups/enki/questboard/
find /var/backups/questboard -name 'questboard-*.sql.gz' -mtime +30 -delete
```

(SSH key from enki's `questboard` user to zephyr's relevant home needs to be set up out-of-band.)

---

## 9. Operational runbook bits

- **View logs:** `journalctl -u questboard.service -f`
- **Reload economy.yaml:** `sudo systemctl kill -s HUP questboard.service`
- **Inspect ledger:** `psql questboard -c "SELECT reason, count(*), sum(amount) FROM xp_transactions GROUP BY reason;"`
- **Database migration (Alembic):** `cd /opt/questboard && sudo -u questboard .venv/bin/alembic upgrade head`
- **Rebuild xp_balance cache after manual ledger surgery:**
  ```sql
  UPDATE users u SET xp_balance = COALESCE((SELECT sum(amount) FROM xp_transactions WHERE user_id = u.id), 0);
  ```

---

## 10. Outstanding pre-launch items

- [ ] Install Postgres on enki
- [ ] Install OAuth extension on NB wiki + register consumer (§3)
- [ ] Add `nbquests.nthmost.net` A record at Gandi
- [ ] Disable / remove the old `maxheadroom` nginx site
- [ ] Decide whether to also remove enki's `nginx` entirely if no other site needs it (probably not — keep it for the API)
- [ ] Set up `questboard` user's SSH key on zephyr for backups
