#!/usr/bin/env bash
# One-time (and whenever a key changes) deploy setup, run from anywhere: bash scripts/modal-setup.sh
#   1. writes .env.modal: .env without the Modal deploy tokens and the database password (git-ignored)
#   2. uploads it as the Modal secret `chimera-lab` (the deployed app's settings)
#   3. stores the Modal deploy tokens as GitHub Actions secrets (the deploy workflow logs in with them)
# Values are read from .env and never printed.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
PY="$ROOT/.venv/Scripts/python.exe"
[ -x "$PY" ] || PY="$ROOT/.venv/bin/python"
[ -f .env ] || { echo "No .env in $ROOT"; exit 1; }

value() { grep -E "^$1=" .env | head -n1 | cut -d= -f2- | tr -d '\r"' | sed -e 's/^ *//' -e 's/ *$//'; }
MODAL_TOKEN_ID="$(value MODAL_TOKEN_ID)"
MODAL_TOKEN_SECRET="$(value MODAL_TOKEN_SECRET)"
[ -n "$MODAL_TOKEN_ID" ] && [ -n "$MODAL_TOKEN_SECRET" ] || { echo "Set MODAL_TOKEN_ID and MODAL_TOKEN_SECRET in .env"; exit 1; }
export MODAL_TOKEN_ID MODAL_TOKEN_SECRET PYTHONWARNINGS=ignore

grep -v -E '^\s*(MODAL_|SUPABASE_DB_URL)' .env > .env.modal
echo "1/3 .env.modal written with: $(grep -E '^[A-Z_]+=' .env.modal | cut -d= -f1 | tr '\n' ' ')"

"$PY" -m modal secret create chimera-lab --from-dotenv .env.modal --force >/dev/null
echo "2/3 Modal secret 'chimera-lab' saved"

if command -v gh >/dev/null 2>&1; then
  printf '%s' "$MODAL_TOKEN_ID" | gh secret set MODAL_TOKEN_ID >/dev/null
  printf '%s' "$MODAL_TOKEN_SECRET" | gh secret set MODAL_TOKEN_SECRET >/dev/null
  echo "3/3 GitHub secrets MODAL_TOKEN_ID and MODAL_TOKEN_SECRET saved"
else
  echo "3/3 skipped: install the GitHub CLI (gh) or add the two secrets in the repo settings"
fi
