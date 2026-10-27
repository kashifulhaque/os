#!/usr/bin/env bash
# Deploys this checkout. This host is the server, so there is nothing to ship:
# pull, then rebuild and restart the container.
#
#   ./scripts/deploy.sh
#
# `.env` is never touched: it holds the SSO secret and is not in the repository.

set -euo pipefail

cd "$(dirname "$0")/.."

git pull --ff-only
SHA="$(git rev-parse --short HEAD)"

echo "Building $SHA"
GIT_SHA="$SHA" docker compose up -d --build

# Each rebuild leaves build cache behind. Keep the recent layers, drop the rest.
docker builder prune -f --filter until=72h >/dev/null 2>&1 || true

echo "Waiting for the health check to report $SHA"
for _ in $(seq 1 60); do
  reported="$(curl -fsS http://127.0.0.1:8098/api/health 2>/dev/null \
    | python3 -c "import json,sys; print(json.load(sys.stdin).get('commit',''))" 2>/dev/null || true)"
  if [ "$reported" = "$SHA" ]; then
    echo "Live at $SHA"
    exit 0
  fi
  sleep 5
done

echo "The app did not report $SHA within five minutes. Check the logs:" >&2
echo "  docker compose logs --tail 60" >&2
exit 1
