# Deploying the feature graph to graph.actropolis.org

> **Status: LIVE** as of 2026-10-26 — `https://graph.actropolis.org/` (served
> from zephyr, Let's Encrypt cert auto-renewing). The steps below are the
> record of how it was set up and how to re-publish / tear down.

Serves `docs/graph.html` + `docs/index.json` as a static page at
**https://graph.actropolis.org/**. Not linked anywhere; `noindex` is set in the
HTML. Privacy is just the unadvertised subdomain (note: the TLS cert lands in
public Certificate Transparency logs, so the hostname is discoverable — fine per
your call; add Basic Auth later if that changes).

**Chosen values:**

| | |
|---|---|
| Host | `graph.actropolis.org` → `149.28.77.210` (zephyr, same IP as quests) |
| Served dir (zephyr) | `/var/www/graph.actropolis.org/` |
| URL | `https://graph.actropolis.org/` |

---

## 1. DNS (Gandi)

Add an **A record**: `graph.actropolis.org` → `149.28.77.210`.

Wait for it, then verify from anywhere:
```bash
dig +short graph.actropolis.org        # expect 149.28.77.210
```

## 2. Copy the two files to zephyr

From this repo on the Mac (regenerate the index first so it's current):
```bash
cd ~/projects/actropolis/quest-board
.venv/bin/python -m scripts.build_docs_index          # refresh docs/index.json
scp docs/graph.html docs/index.json zephyr:/tmp/
```

On zephyr, move them into the web root:
```bash
sudo mkdir -p /var/www/graph.actropolis.org
sudo mv /tmp/graph.html /tmp/index.json /var/www/graph.actropolis.org/
sudo chown -R www-data:www-data /var/www/graph.actropolis.org
```

## 3. Apache vhost (zephyr)

`/etc/apache2/sites-available/graph.actropolis.org.conf`:
```apache
<VirtualHost *:80>
    ServerName graph.actropolis.org
    DocumentRoot /var/www/graph.actropolis.org

    DirectoryIndex graph.html
    <Directory /var/www/graph.actropolis.org>
        Options -Indexes
        AllowOverride None
        Require all granted
    </Directory>

    ErrorLog  ${APACHE_LOG_DIR}/graph.actropolis.org-error.log
    CustomLog ${APACHE_LOG_DIR}/graph.actropolis.org-access.log combined
</VirtualHost>
```

Enable + reload, then let certbot add HTTPS (it rewrites the vhost for :443 and
adds the HTTP→HTTPS redirect):
```bash
sudo a2ensite graph.actropolis.org
sudo apache2ctl configtest && sudo systemctl reload apache2
sudo certbot --apache -d graph.actropolis.org
```

## 4. Verify
```bash
curl -sI https://graph.actropolis.org/ | head -1    # 200
```
Open `https://graph.actropolis.org/` in a browser — the graph should render
(nodes colored by status, click for details, legend filters by status).

---

## Updating the graph later

After editing any design doc's frontmatter:
```bash
cd ~/projects/actropolis/quest-board
.venv/bin/python -m scripts.build_docs_index
scp docs/graph.html docs/index.json zephyr:/tmp/ && \
  ssh zephyr 'sudo mv /tmp/graph.html /tmp/index.json /var/www/graph.actropolis.org/ && \
    sudo chown www-data:www-data /var/www/graph.actropolis.org/*'
```
(`graph.html` only changes when you edit the viewer; `index.json` changes every
regen. The viewer fetches `index.json` with `cache: no-store`, so a browser
refresh always shows the latest.)

## Taking it down

```bash
sudo a2dissite graph.actropolis.org && sudo systemctl reload apache2
```
