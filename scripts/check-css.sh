#!/usr/bin/env bash
# Enforces TASKSHEET Section 6:
#  - theme.css is the only CSS file in frontend/src
#  - no inline style props in .tsx
#  - no CSS modules / CSS-in-JS imports
#  - no raw hex colors in theme.css outside the :root and theme-override token blocks
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SRC="$ROOT/frontend/src"
fail=0

others=$(find "$SRC" -name '*.css' ! -path "$SRC/styles/theme.css" -o -name '*.scss' -o -name '*.module.*' | sort)
if [ -n "$others" ]; then echo "✗ extra stylesheet(s):"; echo "$others"; fail=1; fi

if grep -rnE 'style=\{' "$SRC" --include='*.tsx'; then echo "✗ inline style props found (above)"; fail=1; fi
if grep -rnE "from ['\"](styled-components|@emotion|@stitches)" "$SRC"; then echo "✗ CSS-in-JS import found"; fail=1; fi
css_imports=$(grep -rnE "import ['\"].*\.css['\"]" "$SRC" --include='*.ts' --include='*.tsx' | grep -v 'src/main.tsx:.*styles/theme.css' || true)
if [ -n "$css_imports" ]; then echo "✗ CSS imported outside main.tsx:"; echo "$css_imports"; fail=1; fi

# Hex colors are only allowed inside ":root {" and ":root[data-theme=...] {" blocks.
awk '
  /^:root(\[data-theme="[a-z]+"\])? \{/ { in_tokens = 1 }
  in_tokens && /^\}/ { in_tokens = 0; next }
  !in_tokens && /#[0-9a-fA-F][0-9a-fA-F][0-9a-fA-F]/ { print FILENAME ":" NR ": " $0; bad = 1 }
  END { exit bad }
' "$SRC/styles/theme.css" || { echo "✗ raw hex color outside token blocks (above)"; fail=1; }

if [ "$fail" -eq 0 ]; then echo "✓ CSS rules hold (single theme.css, no inline styles, hex only in tokens)"; fi
exit "$fail"
