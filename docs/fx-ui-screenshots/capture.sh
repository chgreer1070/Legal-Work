#!/usr/bin/env bash
# Regenerate all FX UI tour screenshots.
# Requires: running FX app on localhost:5000, Playwright driver installed.
# Usage: bash docs/fx-ui-screenshots/capture.sh

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
OUTDIR="$REPO_ROOT/docs/fx-ui-screenshots"
DRIVER="$REPO_ROOT/.claude/skills/run-fx/driver.mjs"
BASE="http://localhost:5000"

shot() { node "$DRIVER" shot "$1" "$2" >/dev/null && echo "  captured $2"; }

echo "Capturing FX UI screenshots..."

# Pages that render with seed data alone
shot "$BASE/fx/"              "$OUTDIR/01-dashboard.png"
shot "$BASE/fx/contracts"     "$OUTDIR/02-contracts-list.png"
shot "$BASE/fx/contracts/1"   "$OUTDIR/03-contract-detail.png"

# Alerts (may be empty if no thresholds breached)
shot "$BASE/fx/alerts"        "$OUTDIR/04-alerts-list.png"

# Alert detail states require a real alert -- capture if alert #1 exists
if curl -sf "$BASE/fx/api/alerts/1" >/dev/null 2>&1; then
  shot "$BASE/fx/alerts/1" "$OUTDIR/05-alert-detail-triggered.png"
else
  echo "  skipped alert-detail screenshots (no alert #1)"
fi

# Predictions (empty unless previously run)
shot "$BASE/fx/predictions"   "$OUTDIR/06-predictions.png"

# Audit log
shot "$BASE/fx/audit"         "$OUTDIR/07-audit-log.png"

echo "Done. Screenshots saved to $OUTDIR/"
