# Legal-Work — Claude Code Project Notes

This repo contains two unrelated apps:

1. **FX Recovery System** (`fx/`, `fx_app.py`) — the active project. Monitors FX adjustment clauses in commercial contracts, triggers alerts when rates breach thresholds, drafts customer notifications via Claude, and routes them through human approval.
2. **Legacy converter** (`app.py`, `converter.py`, `templates/`, `static/`) — standalone Flask app, not part of FX work. Don't touch unless explicitly asked.

## Branch convention (REQUIRED)

All work must be committed to a branch named `claude/<feature-slug>-<session-id>`. The git proxy rejects pushes to any other branch with HTTP 403. The session prompt always specifies the exact branch name to use.

## How to run the FX app

```bash
# Reset and seed fresh data
rm -f fx_recovery.db fx_recovery.db-shm fx_recovery.db-wal
python -m fx.mock.seed

# Start the app (scheduler off for manual testing)
FX_SCHEDULER_ENABLED=false python fx_app.py
# → http://localhost:5000/fx/

# Trigger a rate refresh + threshold check
curl -X POST http://localhost:5000/fx/api/rates/refresh
```

Slash commands available: `/fx-run`, `/fx-reset`, `/fx-stress`.

## How to run stress tests

```bash
# DB & logic stress (no HTTP, ~5s)
python stress_tests/db_stress_test.py

# HTTP load test (requires running app)
locust -f stress_tests/locustfile.py --host=http://localhost:5000 \
       --headless -u 50 -r 10 -t 60s
```

Last verified results: 0% failures across 2,596 requests, p95 22ms, p99 82ms.

## Sandbox limitations (IMPORTANT — read before debugging)

This Claude Code sandbox has constraints that look like bugs but aren't:

- **No outbound HTTPS to most hosts.** The live FX feed (`FX_FEED_SOURCE=exchangerate_host`) **will always fail here** and fall back to mock. That's the designed resilience path, not a regression. Test the fallback by reading the `WARNING ... falling back to mock` log line.
- **GitHub API works via the agent proxy, but repo access needs the Claude GitHub App.** `gh` is installed by the SessionStart hook. `gh api` REST calls are proxied with real auth and succeed for identity (`gh api user` → the account login), but repo operations (list/create/merge PRs) return **HTTP 403 "GitHub access is not enabled … connect the Claude GitHub App"** until an account/org admin connects the Claude GitHub App. GraphQL is **not** proxied, so high-level `gh pr`/`gh issue` commands (which use GraphQL) fail — use `gh api` REST endpoints instead. The git proxy at `127.0.0.1:*` handles push/pull for the **designated branch only** (other branches 403).
- **No Anthropic API access by default** unless `ANTHROPIC_API_KEY` is set in the env. Clause extraction and notification generation degrade gracefully.

## Current state of the FX system

- ✅ 15 hardening fixes landed in `14e94a9` (DB WAL+FK, exposure formula, z-score math, state machine, audit logging, retry helper, scheduler app context)
- ✅ Stress test suite landed (`stress_tests/`)
- ✅ Live exchangerate.host feed integrated with mock fallback (`44a1b9a`)
- ❌ No unit/integration tests yet — only stress tests
- ❌ No PR opened (must be created manually via GitHub web UI)

## Key files

| File | Purpose |
|---|---|
| `fx_app.py` | Flask app factory, registers `/fx/` blueprint |
| `fx/config.py` | All env-var configuration |
| `fx/db.py` | SQLAlchemy engine, WAL mode, FK enforcement |
| `fx/models.py` | All ORM models (Contract, FXClause, FXRate, Alert, Prediction, Transaction, AuditEntry) |
| `fx/routes/` | REST API blueprints |
| `fx/monitoring/fx_feed.py` | Mock + live exchangerate.host feed with fallback |
| `fx/monitoring/threshold_checker.py` | Compares rates vs clauses, creates alerts |
| `fx/monitoring/scheduler.py` | APScheduler background jobs (Flask app context wrapper) |
| `fx/exposure/calculator.py` | `volume × \|rate_delta\|` exposure |
| `fx/prediction/forecaster.py` | Moving-avg + Gaussian z-score forecasting |
| `fx/notifications/approval.py` | State machine: triggered → pending_approval → approved → sent |
| `fx/audit/logger.py` | SOX-compliant audit log |
| `fx/utils.py` | `call_claude_with_retry()` exponential backoff helper |
| `stress_tests/locustfile.py` | HTTP load test (3 user classes) |
| `stress_tests/db_stress_test.py` | DB concurrency tests |

## Conventions

- **No emojis** in code or commits unless explicitly asked
- **No new tests/docs** unless asked — the user will tell you when
- **Honest about limits**: when describing accuracy of forecasting/exposure, be candid that the math is prototype-grade
- **Mock fallback is a feature, not a bug** — the live FX feed must never crash the monitoring loop

## Things the user often asks (cheat sheet)

- "How do I see this thing?" → Run `/fx-run`, then visit `http://localhost:5000/fx/` *on the same machine* (localhost doesn't work from a phone)
- "Create a PR" → Cannot from sandbox; give them the GitHub URL `https://github.com/<owner>/Legal-Work/compare/master...claude/<branch>` to open manually
- "What does this output mean?" → Lead with what the numbers say, then caveats about prototype-grade math
