#!/usr/bin/env bash
# Runs the backend (uvicorn, live models) and the frontend (Vite) together for development.
# Keys come from the repo-root .env (see .env.example). Open http://localhost:5173: the Vite dev server proxies
# /evo and /health to the backend, so the browser sees one origin, as in production.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PY="${PYTHON:-$ROOT/.venv/bin/python}"
[ -x "$PY" ] || PY="$ROOT/.venv/Scripts/python.exe"
[ -x "$PY" ] || PY=python3
BACKEND_PORT="${BACKEND_PORT:-8000}"

cleanup() { kill 0 2>/dev/null || true; }
trap cleanup EXIT INT TERM

(cd "$ROOT" && "$PY" -m uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port "$BACKEND_PORT" --reload --reload-dir backend/app) &
(cd "$ROOT/frontend" && CHIMERA_BACKEND_URL="http://127.0.0.1:$BACKEND_PORT" npm run dev) &
echo "Chimera Lab: http://localhost:5173 (backend on :$BACKEND_PORT)"
wait
