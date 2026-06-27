#!/usr/bin/env bash
# Starts the backend (FastAPI via uv) and frontend (Vite via bun) dev servers.
# Ctrl+C (or any TERM) stops both, including their child processes, leaving
# nothing running and no artifacts behind.

set -euo pipefail
set -m # job control: each background job gets its own process group, so a
       # single `kill` on the group takes down all of its descendants too.

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
export PATH="$HOME/.local/bin:$HOME/.bun/bin:$PATH"

BACKEND_PID=""
FRONTEND_PID=""

wait_for_exit() {
  local pid="$1" i=0
  while kill -0 "$pid" 2>/dev/null && (( i < 25 )); do
    sleep 0.2
    i=$((i + 1))
  done
}

cleanup() {
  trap - EXIT INT TERM
  echo
  echo "Stopping..."

  for pid in "$BACKEND_PID" "$FRONTEND_PID"; do
    [[ -n "$pid" ]] || continue
    kill -TERM "-$pid" 2>/dev/null || kill -TERM "$pid" 2>/dev/null || true
  done

  for pid in "$BACKEND_PID" "$FRONTEND_PID"; do
    [[ -n "$pid" ]] || continue
    wait_for_exit "$pid"
    if kill -0 "$pid" 2>/dev/null; then
      kill -KILL "-$pid" 2>/dev/null || kill -KILL "$pid" 2>/dev/null || true
    fi
  done

  wait 2>/dev/null || true
  echo "Stopped — no backend/frontend processes left running."
}

trap cleanup EXIT INT TERM

if [[ ! -d "$ROOT_DIR/frontend/node_modules" ]]; then
  echo "Installing frontend dependencies..."
  (cd "$ROOT_DIR/frontend" && bun install)
fi

echo "Starting backend  -> http://localhost:8000"
(cd "$ROOT_DIR/backend" && uv run uvicorn main:app --reload --port 8000) &
BACKEND_PID=$!

echo "Starting frontend -> http://localhost:5173"
(cd "$ROOT_DIR/frontend" && bun run dev) &
FRONTEND_PID=$!

echo "Both running. Press Ctrl+C to stop."
wait -n "$BACKEND_PID" "$FRONTEND_PID"
