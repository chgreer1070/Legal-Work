#!/bin/bash
# SessionStart hook: pre-install Python deps so the sandbox is usable out of the box.
# Idempotent — safe to run every session start.
set -euo pipefail

# Only run in remote Claude Code sessions (sandbox with fresh environment).
if [ "${CLAUDE_CODE_REMOTE:-}" != "true" ]; then
  exit 0
fi

REPO_DIR="${CLAUDE_PROJECT_DIR:-$(dirname "$(dirname "$(dirname "$(readlink -f "$0")")")")}"

# Sandbox quirk: packages managed by system, need --break-system-packages + --ignore-installed
PIP_FLAGS="--break-system-packages --ignore-installed --quiet"

# ContractTwin (Flask + mammoth) — lightweight, always install.
if [ -f "$REPO_DIR/requirements-contracttwin.txt" ]; then
  python3 -m pip install $PIP_FLAGS -r "$REPO_DIR/requirements-contracttwin.txt" || true
fi

# Converter (heavy stack) — install best-effort; some packages are wheels-only.
if [ -f "$REPO_DIR/requirements-converter.txt" ]; then
  python3 -m pip install $PIP_FLAGS -r "$REPO_DIR/requirements-converter.txt" --only-binary=:all: || true
fi

# Expose FLASK_APP so `flask run` works without extra setup.
if [ -n "${CLAUDE_ENV_FILE:-}" ]; then
  echo 'export FLASK_APP=app.py' >> "$CLAUDE_ENV_FILE"
fi
