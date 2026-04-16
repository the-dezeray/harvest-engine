#!/usr/bin/env bash
set -euo pipefail

# Run from repo root (directory of this script)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

require_cmd() {
  command -v "$1" >/dev/null 2>&1 || {
    echo "Missing required command: $1" >&2
    exit 1
  }
}

require_cmd docker
require_cmd uv
require_cmd npm

echo "==> docker compose down"
# down can fail if nothing is running; don't treat that as fatal
set +e
docker compose down
set -e

echo "==> docker compose up -d --build"
docker compose up -d --build

echo "==> starting emitter (uv run emitter/emitter.py)"
uv run emitter/emitter.py &
EMITTER_PID=$!

echo "==> starting frontend (npm run dev)"
(
  cd frontend
  npm run dev
) &
FRONTEND_PID=$!

cleanup() {
  echo
  echo "==> stopping emitter/frontend"
  kill "$EMITTER_PID" "$FRONTEND_PID" >/dev/null 2>&1 || true
}
trap cleanup EXIT INT TERM

echo ""
echo "Emitter PID:   $EMITTER_PID"
echo "Frontend PID:  $FRONTEND_PID"
echo ""
echo "Press Ctrl+C to stop emitter/frontend (containers stay up)."

wait "$EMITTER_PID" "$FRONTEND_PID"
