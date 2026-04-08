# CLAUDE.md

Guidance for AI assistants (Claude Code, etc.) working in this repository.

## Repository overview

This repo hosts **two cooperating Flask applications** that share a single Python
process when launched via the unified entry point. They are independent in
purpose but live in the same codebase and can be developed in tandem.

1. **Outlook-to-PDF Converter** — `app.py` + `converter.py`
   Drag-and-drop web UI that converts `.msg` emails (with attachments) and
   Office documents (`.doc`, `.docx`, `.ppt`, `.pptx`, `.pdf`) to PDF, bundles
   the results, and serves them as a downloadable zip. Templates live in
   `templates/`, static assets in `static/css` and `static/js`.

2. **FX Recovery System** — `fx/` package + `fx_app.py`
   SQLite-backed contract monitoring system that ingests customer contracts,
   uses the Claude API to extract FX adjustment clauses, polls FX rates on a
   schedule, raises alerts when contractual thresholds are breached, and drafts
   formal customer notifications (gated behind human approval). Templates are
   under `fx_templates/`, static assets under `static/fx/`. Mounted at `/fx`.

`fx_app.py` is the **canonical entry point** for running both apps together —
it imports the converter app, registers the FX blueprint at `/fx`, initialises
the database, and starts the background scheduler.

## Layout

```
.
├── app.py                  # Outlook-to-PDF Flask app (legacy standalone)
├── converter.py            # Email + Office → PDF conversion logic
├── fx_app.py               # Unified entry: mounts converter + /fx blueprint
├── run.sh                  # Convenience script — runs ONLY the legacy app.py
├── requirements.txt
├── templates/              # Converter Jinja templates (index.html)
├── static/{css,js}/        # Converter static assets
├── fx_templates/           # FX Recovery Jinja templates
├── static/fx/{css,js}/     # FX Recovery static assets
├── stress_tests/           # Locust + DB stress harness
└── fx/                     # FX Recovery package
    ├── __init__.py         # create_fx_blueprint()
    ├── config.py           # All env-driven settings
    ├── db.py               # SQLAlchemy engine, Base, init_db, get_session
    ├── models.py           # Contract, FXClause, FXRate, Alert, Prediction,
    │                       # Transaction, AuditEntry
    ├── utils.py            # call_claude_with_retry()
    ├── audit/logger.py     # log_event() — SOX audit trail w/ prompt hashes
    ├── ingestion/          # parser.py, clause_extractor.py, schema.py
    ├── exposure/           # calculator.py, transaction_data.py
    ├── monitoring/         # fx_feed.py, rate_cache.py, scheduler.py,
    │                       # threshold_checker.py
    ├── prediction/         # features.py, forecaster.py
    ├── notifications/      # generator.py, approval.py
    ├── mock/               # Seed data for demos / tests
    └── routes/             # dashboard.py, contracts.py, alerts.py, api.py
```

## Running

```bash
# Install deps (system libs needed: libreoffice, weasyprint deps)
pip install -r requirements.txt

# Unified app (converter + FX system at /fx) — preferred
python fx_app.py

# Converter only (no FX) — also what run.sh does
python app.py            # or: ./run.sh
```

Both serve on `http://0.0.0.0:5000`. The converter UI is at `/`, the FX
dashboard at `/fx/`.

### Key environment variables

| Variable | Default | Purpose |
|---|---|---|
| `ANTHROPIC_API_KEY` | *(unset)* | Required for FX clause extraction and notification drafting |
| `FX_CLAUDE_MODEL` | `claude-sonnet-4-20250514` | Claude model used by FX system |
| `FX_DATABASE_PATH` | `fx_recovery.db` | SQLite file path |
| `FX_FEED_SOURCE` | `mock` | `mock`, `exchangerate_host`, or `oanda` |
| `FX_DEMO_MODE` | `deterministic` | `deterministic` or `random` mock walk |
| `FX_RATE_INTERVAL` | `15` | Minutes between rate fetches |
| `FX_THRESHOLD_INTERVAL` | `60` | Minutes between threshold checks |
| `FX_SCHEDULER_ENABLED` | `true` | Set `false` to disable background jobs (e.g. for load tests) |
| `FX_UPLOAD_DIR` | `fx_uploads` | Where uploaded contracts are stored |

The FX system **falls back to mock rates** if the configured live source fails,
so the monitoring loop never crashes when the network is unavailable.

## Tests / stress

There is no unit test suite. Stress and load tests live in `stress_tests/`:

```bash
# DB & business logic stress (no server)
python stress_tests/db_stress_test.py

# HTTP load via Locust — disable scheduler to avoid contention
FX_SCHEDULER_ENABLED=false python fx_app.py &
locust -f stress_tests/locustfile.py --host=http://localhost:5000 \
       --headless -u 50 -r 5 -t 3m
```

Targets: read-endpoint p95 < 500 ms, write < 2 s, 0% failures on reads. Watch
for `database is locked` messages — SQLite is in WAL mode (`fx/db.py`) but
heavy concurrent writes can still contend.

## Architecture conventions

### Database (FX system)

- SQLAlchemy 2.x **typed declarative** models in `fx/models.py` (`Mapped[...]`,
  `mapped_column`). All models have a `to_dict()` method used by the JSON API.
- SQLite with `journal_mode=WAL` and `foreign_keys=ON` set per connection in
  `fx/db.py`. `check_same_thread=False` so the scheduler thread can share the
  engine.
- Sessions are obtained via `from fx.db import get_session` and **must be
  closed in a `finally` block**. The route handlers in `fx/routes/` follow this
  pattern consistently — match it.
- Currency / rate fields use `Numeric(18, 6)`; monetary fields use
  `Numeric(18, 2)`. Convert to `float` only at the JSON boundary.

### Claude API usage

- Always go through `fx.utils.call_claude_with_retry()` — it handles
  `RateLimitError` and `APIConnectionError` with exponential backoff.
- The default model is read from `fx.config.CLAUDE_MODEL`. Don't hardcode model
  names in business logic.
- `clause_extractor.py` and `notifications/generator.py` are the only callers
  today. Both log full prompt + response to the audit trail.
- The notification system prompt explicitly treats `<contract_clause>...
  </contract_clause>` content as data, not instructions — preserve that pattern
  if you add new prompts that include user-supplied text.

### Audit trail (SOX-relevant)

- Every state-changing operation in the FX system **must** call
  `fx.audit.logger.log_event(...)`. See examples in `routes/contracts.py`,
  `monitoring/threshold_checker.py`, `notifications/approval.py`.
- For AI calls, pass `ai_prompt=` and `ai_response=`. The logger stores SHA-256
  hashes plus the full text in `details` for later verification.
- Prefer passing the active session via `session=` so the audit row commits
  atomically with the change it describes.

### Alert state machine

`triggered` → `pending_approval` → `approved` → `sent`
            ↘ `dismissed`

- Alerts are created by `monitoring/threshold_checker.py` with status
  `triggered`. The checker skips clauses that already have an open alert in
  any non-terminal state.
- Notifications are drafted via `notifications/generator.py` (moves alert to
  `pending_approval`). Generated text **never auto-sends** — it requires an
  explicit `approve` then `send` call from `notifications/approval.py`.

### Scheduler

- `fx/monitoring/scheduler.py` uses APScheduler `BackgroundScheduler` started
  by `fx_app.create_app()`. Two jobs: rate fetch and threshold check. Both
  enter the Flask app context before running.
- For tests / load runs, set `FX_SCHEDULER_ENABLED=false` to keep the loop
  out of the way.

### Converter

- Conversion is offloaded to a daemon thread in `app.py:_run_conversion`. Job
  state lives in an in-memory dict guarded by `_jobs_lock`. **There is no
  persistence** — restarting the app loses job history.
- `.msg` files are processed first so attachments end up in the same email's
  output sub-folder.
- Conversion strategy in `converter.py:convert_office_to_pdf`:
  - `.docx` → `mammoth` → HTML → `weasyprint` (preferred), LibreOffice
    headless as fallback.
  - `.doc` / `.ppt` → LibreOffice headless only.
  - `.pptx` → `python-pptx` text extraction → `reportlab` (preferred),
    LibreOffice as fallback.
  - `.pdf` → copied with metadata stamped via `pypdf`.
- All output PDFs get email metadata stamped via `_stamp_pdf_metadata`. When
  adding a new converter path, follow the same temp-file → stamp → move
  pattern.

## Coding conventions

- Python ≥ 3.10 syntax is in use (`int | None`, `dict[str, ...]`, PEP 604).
- Type hints are used pragmatically — annotate new public functions, don't
  retrofit untyped helpers unless touching them.
- Module docstrings are short and describe the file's purpose; functions get a
  one-line docstring when their behaviour isn't obvious from the signature.
- Imports are grouped: stdlib, third-party, local, with a blank line between
  groups. Local imports are absolute (`from fx.db import ...`).
- Errors at API boundaries return JSON with an `error` key and an appropriate
  HTTP status; don't let exceptions escape the route handlers.
- Don't add new dependencies without updating `requirements.txt`. Pin lower
  bounds the same way existing entries do (`flask>=3.0`, etc.).

## Things to avoid

- **Don't auto-send notifications.** The approval gate exists for compliance
  reasons. Anything that bypasses `notifications/approval.py` is a bug.
- **Don't write to the converter's `_jobs` dict without `_jobs_lock`.**
- **Don't bypass `call_claude_with_retry`.** Direct `client.messages.create`
  calls won't get retry/backoff and won't be uniformly logged.
- **Don't commit `fx_recovery.db`, `uploads/`, `output/`, `fx_uploads/`, or
  `.env*`** — all are listed in `.gitignore`.
- **Don't add unit tests under random paths.** There is no test suite yet; if
  you introduce one, place it in a top-level `tests/` directory and update
  this file.

## Git workflow

- Default branch is `main`. The repo on GitHub is `chgreer1070/legal-work`.
- Feature work happens on `claude/<topic>-<suffix>` branches (see existing
  `claude/add-claude-documentation-*`, `claude/fx-recovery-agent-system-*`,
  `claude/outlook-to-pdf-converter-*` branches).
- Push only to the branch you were assigned. Don't open PRs unless explicitly
  asked.
