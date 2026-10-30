#!/usr/bin/env bash
# Runs the backend (uvicorn, mock mode) and the frontend (Vite) together.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PY="${PYTHON:-$ROOT/.venv/bin/python}"
[ -x "$PY" ] || PY=python3
export CHIMERA_MODE="${CHIMERA_MODE:-mock}"
export MOCK_DELAY_SCALE="${MOCK_DELAY_SCALE:-1}"
BACKEND_PORT="${BACKEND_PORT:-8000}"

cleanup() { kill 0 2>/dev/null || true; }
trap cleanup EXIT INT TERM

(cd "$ROOT/backend" && "$PY" -m uvicorn app.main:app --host 127.0.0.1 --port "$BACKEND_PORT" --reload --reload-dir app) &
(cd "$ROOT/frontend" && VITE_API_BASE_URL="${VITE_API_BASE_URL:-http://localhost:$BACKEND_PORT}" npm run dev -- ${VITE_MODE:+--mode "$VITE_MODE"}) &
echo "Chimera Lab: backend http://localhost:$BACKEND_PORT (mode $CHIMERA_MODE), frontend http://localhost:5173"
wait
