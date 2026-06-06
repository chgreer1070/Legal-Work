#!/bin/bash
set -euo pipefail

if [ "${CLAUDE_CODE_REMOTE:-}" != "true" ]; then
  exit 0
fi

pip install --ignore-installed blinker flask anthropic pydantic sqlalchemy \
  apscheduler requests python-dotenv numpy pytest pytest-mock reportlab \
  2>&1 | tail -1

(cd "$CLAUDE_PROJECT_DIR/.claude/skills/run-fx" && npm install --no-audit --no-fund 2>&1 | tail -1)
