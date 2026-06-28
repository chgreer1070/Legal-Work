#!/usr/bin/env bash
# Read-only session orientation. Run this FIRST in a new or resumed session,
# before editing or pushing. It surfaces the three things that caused wasted
# work in the past: stale checkouts, branch-vs-origin drift, and the per-session
# GitHub proxy gate. Makes no changes — safe to run anytime.
set -uo pipefail
cd "$(git rev-parse --show-toplevel 2>/dev/null || echo .)" || exit 0

echo "== git =="
branch=$(git branch --show-current 2>/dev/null || echo "?")
echo "branch:   $branch"
echo "HEAD:     $(git rev-parse --short HEAD 2>/dev/null)  $(git log -1 --format='%s' 2>/dev/null)"
if up=$(git rev-parse --short '@{u}' 2>/dev/null); then
  read -r behind ahead < <(git rev-list --left-right --count '@{u}...HEAD' 2>/dev/null || echo "0 0")
  echo "upstream: $up  (ahead ${ahead:-0} / behind ${behind:-0})"
  [ "${behind:-0}" -gt 0 ] && echo "  ! behind upstream — consider: git pull --ff-only"
else
  echo "upstream: (none — branch not pushed yet?)"
fi
dirty=$(git status --porcelain 2>/dev/null)
if [ -n "$dirty" ]; then
  echo "worktree: DIRTY"; echo "$dirty" | sed 's/^/  /'
else
  echo "worktree: clean"
fi
echo "  note: if the code on disk doesn't match what the task context says was"
echo "  committed, you may be on a STALE checkout — reconcile before editing, and"
echo "  don't re-implement work the canonical branch already has."

echo
echo "== github =="
if command -v gh >/dev/null 2>&1; then
  echo "gh:       $(gh --version 2>/dev/null | head -1)"
  echo "identity: $(gh api user --jq '.login' 2>/dev/null || echo '?')"
  slug=$(git remote get-url origin 2>/dev/null | sed -E 's#.*/git/##; s#\.git$##')
  if [ -n "${slug:-}" ] && gh api "repos/$slug" --jq '.full_name' >/dev/null 2>&1; then
    echo "repo API: OK ($slug) — PRs/merges available via 'gh api' REST"
  else
    echo "repo API: GATED (403 'not enabled for this session')"
    echo "  -> a fresh session is required; resuming or retrying does NOT lift it."
    echo "  -> confirm the Claude GitHub App is connected for this account/repo."
  fi
else
  echo "gh:       not installed (the SessionStart hook installs it)"
fi
