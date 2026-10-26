#!/usr/bin/env bash
# Regenerate the design-docs feature graph and publish it to graph.actropolis.org.
# Run from anywhere in the repo. The contract this enforces is docs/GRAPH.md;
# first-time server setup is docs/graph-deploy.md.
set -euo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO"

PY="${PY:-.venv/bin/python}"
command -v "$PY" >/dev/null 2>&1 || PY=python3
HOST="${GRAPH_HOST:-zephyr}"
DEST="/var/www/graph.actropolis.org"

echo "==> regenerating docs/index.json + docs/OVERVIEW.md"
"$PY" -m scripts.build_docs_index

# Refuse to publish a broken graph.
DANGLING="$("$PY" -c "import json;print(len(json.load(open('docs/index.json'))['dangling_edges']))")"
if [ "$DANGLING" != "0" ]; then
  echo "ERROR: $DANGLING dangling edge target(s) in index.json — fix before publishing." >&2
  "$PY" -c "import json;print(json.load(open('docs/index.json'))['dangling_edges'])" >&2
  exit 1
fi

echo "==> deploying graph.html + overview.html + index.json to ${HOST}:${DEST}"
scp docs/graph.html docs/overview.html docs/index.json "${HOST}:/tmp/"
ssh "$HOST" "sudo mv /tmp/graph.html /tmp/overview.html /tmp/index.json '${DEST}/' \
  && sudo chown www-data:www-data '${DEST}'/graph.html '${DEST}'/overview.html '${DEST}'/index.json"

echo "==> verifying"
curl -fsS -o /dev/null -w "https://graph.actropolis.org/ -> HTTP %{http_code}\n" https://graph.actropolis.org/

echo "==> published. Now commit the regenerated docs/index.json + docs/OVERVIEW.md."
