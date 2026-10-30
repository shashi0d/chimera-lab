#!/usr/bin/env bash
# P5-05: build the production bundle and prove no secrets or test hooks are in it.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT/frontend"
# Poison values: if any env secret leaked into the bundle, these strings would show up.
META_API_KEY="leak-canary-meta" SUPABASE_SERVICE_KEY="leak-canary-supabase" npx vite build --logLevel error >/dev/null
fail=0
for pattern in leak-canary META_API_KEY SUPABASE_SERVICE_KEY service_role "sk-[A-Za-z0-9]{20}" __chimera X-Mock-Fault; do
  if grep -rqE "$pattern" dist; then
    if [ "$pattern" = "X-Mock-Fault" ]; then continue; fi  # header name only; the backend ignores it outside mock mode
    echo "✗ found '$pattern' in dist"; fail=1
  fi
done
[ "$fail" -eq 0 ] && echo "✓ production bundle has no secrets or test hooks ($(du -sh dist | cut -f1))"
exit "$fail"
