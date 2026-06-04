# Ansible — Future Sketch (non-binding)

A rough idea for when the quest board grows beyond a single host. **No commitment** to this shape; revisit when triggers below actually fire.

---

## When this becomes worth doing

Any one of these crossing a threshold:

- **More than one host** in the circuit. Plausible: enki (API server) + N Raspberry Pis around the hackerspace acting as edge clients (status displays, RFID quest-claim stations, kiosk terminals near the entrance).
- **More than one person deploys.** Once someone other than nthmost is expected to push changes, a shell script that "you have to know how to run" becomes a liability.
- **A staging environment exists.** When you want a VM at home or a second NB box that mirrors prod for testing, encoded provisioning matters.
- **Config drift starts hurting.** Edge devices fall out of sync with the API contract; manual `ssh + apt + restart` across N Pis stops being feasible around N ≈ 4.

If none of the above is true yet, stay on shell scripts.

---

## Plausible fleet shape

```
                ┌─ enki ─────────────────────────────────┐
                │  questboard-api (FastAPI)                  │
                │  postgres                                  │
                │  ollama                                    │
                │  nginx + LE                                │
                └────────────────────────────────────────────┘
                           ▲       ▲       ▲       ▲
                           │ HTTPS │       │       │
                ┌──────────┴──┐ ┌──┴───┐ ┌─┴────┐ ┌┴─────┐
                │ pi-kiosk-1  │ │pi-rfid│ │ pi-display-N │
                │ (touchscreen│ │ (claim│ │  (board view │
                │  near door) │ │  pad) │ │   in church)  │
                └─────────────┘ └──────┘ └────────────────┘
```

Hypothetical roles:
- **`api`** — the enki box itself (what DEPLOYMENT.md describes today).
- **`edge-display`** — Pis running a kiosk-mode browser pointed at a public quest-board view.
- **`edge-rfid`** — Pis with an RFID reader that POST claim events to the API (each Pi has its own service-principal API key).
- **`edge-print`** — a thermal-printer Pi that prints quest cards on demand (ties into the existing `catprinter` work).

---

## Inventory shape

```
ansible/
├── inventory/
│   ├── prod.yml                  # real fleet
│   └── group_vars/
│       ├── all.yml               # api_base_url, common APT pkgs
│       ├── api.yml               # enki-only knobs
│       └── edge.yml              # Pi-only knobs
├── roles/
│   ├── common/                   # user, hostname, base packages, NTP
│   ├── questboard-api/           # what DEPLOYMENT.md becomes
│   ├── questboard-edge-display/
│   ├── questboard-edge-rfid/
│   └── ollama/                   # if/when Pis run their own tiny models
├── playbooks/
│   ├── site.yml                  # full deploy
│   ├── deploy-api-only.yml
│   ├── update-edges.yml          # rolling update across edge fleet
│   └── rotate-edge-keys.yml      # rotate per-device API keys
└── README.md
```

Inventory excerpt:
```yaml
all:
  children:
    api:
      hosts:
        enki: { ansible_host: 10.100.0.4, ansible_user: nthmost }
    edge:
      children:
        edge-display:
          hosts:
            pi-display-church: { ansible_host: 10.21.1.51 }
            pi-display-hackitorium: { ansible_host: 10.21.1.52 }
        edge-rfid:
          hosts:
            pi-rfid-door: { ansible_host: 10.21.1.60 }
```

---

## Migration path from current state

DEPLOYMENT.md is structured intentionally to make the shell-→-Ansible migration cheap. Mapping:

| DEPLOYMENT.md section | Ansible role / task |
|---|---|
| §1 system prerequisites | `roles/common/tasks/apt.yml` |
| §2 service user / filesystem | `roles/common/tasks/users.yml` + `roles/questboard-api/tasks/dirs.yml` |
| §3 wiki OAuth registration | **Stays manual.** Wiki admin action; one-time. Document in role README. |
| §4 Postgres setup | `roles/questboard-api/tasks/postgres.yml` |
| §5 economy.yaml | `roles/questboard-api/templates/economy.yaml.j2` + `notify: reload questboard` |
| §6 systemd unit | `roles/questboard-api/files/questboard.service` |
| §7 nginx + LE | `roles/questboard-api/tasks/nginx.yml` (use `community.crypto.acme_certificate` or shell out to certbot) |
| §8 backups | `roles/questboard-api/templates/backup.sh.j2` + cron module |

The handful of shell scripts in `quest-board/scripts/` (per the v1 plan) become role tasks almost line-for-line.

---

## API/edge contract considerations

If we end up with edge devices, the **biggest design pressure** Ansible will apply is forcing us to think about API versioning early:

- Edges should pin to `/api/v1/...`. When we ship `/api/v2/...`, both versions run side-by-side until edges roll forward.
- Each edge device gets its own service-principal API key (rotated by `playbooks/rotate-edge-keys.yml`).
- Edge code lives in its own small repo (`questboard-edge-client` or per-role repos), versioned and tagged. Ansible deploys a specific tag, not `main`.
- Health-check loop: edges `POST /api/v1/edge/heartbeat` every N minutes. The API records last-seen per device. A staleness check on `/stats` flags edges that haven't phoned home, so we know if a Pi has fallen off the network.

These ideas don't need Ansible — they're just easier to operate at scale once Ansible is in the picture.

---

## Secrets handling

Three plausible options:

1. **Ansible Vault** — encrypt `group_vars/api/secrets.yml` with a passphrase. Standard, integrated, slightly clunky for one-off secret reads.
2. **Continue with `~/projects/nthmost-systems/.secrets/` + rsync** — fetch secrets in a play via `delegate_to: localhost` and templated lookup. Keeps the existing pattern.
3. **External secret store** (Bitwarden CLI, 1Password CLI, `pass`) — overkill for this, but worth knowing exists.

Recommend (2) — it's how nthmost-systems already works, and Ansible-on-top doesn't need to disrupt it.

---

## Triggers that would push this past "future" into "now"

- Provisioning a second device (first Pi).
- Realizing during a 3am outage that we don't remember which file to edit on which host.
- Onboarding a second human to push deployments.
- Wanting to run a staging instance for testing economy.yaml changes against synthetic load before promoting them.

Until one of those happens, keep the shell scripts and a tidy DEPLOYMENT.md.
