---
name: run-fx
description: Run, drive, and screenshot the FX Recovery System (Flask web app at /fx). Use when asked to start, launch, screenshot, smoke-test, or verify the FX dashboard / contracts / alerts UI.
---

# run-fx

Boot the FX Recovery System on `localhost:5000` and drive it headlessly with Playwright.

The FX app is a Flask blueprint mounted at `/fx/` of a unified app in `fx_app.py`. It uses a local SQLite file (`fx_recovery.db`, WAL mode) seeded from `fx.mock.seed`. The driver lives at `.claude/skills/run-fx/driver.mjs` and uses the Playwright + Chromium that ship with this container at `/opt/pw-browsers/chromium-1194/chrome-linux/chrome` — no `playwright install` needed.

All paths below are relative to the **repo root** (`/home/user/Legal-Work`).

## Prerequisites (one-time per fresh container)

```bash
pip install --ignore-installed blinker flask anthropic pydantic sqlalchemy apscheduler requests python-dotenv numpy pytest pytest-mock reportlab
(cd .claude/skills/run-fx && npm install --no-audit --no-fund)
```

The `--ignore-installed blinker` is required: the base image ships a Debian-packaged `blinker` that pip can't uninstall normally; Flask 3 needs a newer one.

`reportlab` is needed only because `fx.mock.sample_contracts` imports it at module load (to render seed PDFs). Skipping it breaks `python -m fx.mock.seed`.

You do **not** need: `weasyprint`, `extract-msg`, `python-docx`, `mammoth`, `red-black-tree-mod`, `locust`. Those belong to the unrelated legacy converter (`app.py`) or to stress testing.

## Run

### Reset, seed, launch

```bash
pkill -f "python fx_app.py" 2>/dev/null
rm -f fx_recovery.db fx_recovery.db-shm fx_recovery.db-wal stress_test.db*
python -m fx.mock.seed
nohup env FX_SCHEDULER_ENABLED=false python fx_app.py > /tmp/fx_app.log 2>&1 < /dev/null &
disown
sleep 3
curl -s -o /dev/null -w "HTTP %{http_code}\n" http://localhost:5000/fx/api/dashboard/summary  # expect 200
```

Seed prints `3 contracts, 4 FX clauses, 90 days of historical rates`. `FX_SCHEDULER_ENABLED=false` stops the APScheduler thread — leave it off for manual testing, otherwise the background loop fights your curls.

`nohup ... &` + `disown` is required: a plain `&` keeps the process tied to the Claude Bash session and it gets reaped when the tool call ends. `nohup` survives.

### Drive the UI (agent path)

```bash
# Full smoke: API summary + dashboard screenshot + click Contracts + count rows
node /home/user/Legal-Work/.claude/skills/run-fx/driver.mjs smoke /tmp

# One-off screenshot
node /home/user/Legal-Work/.claude/skills/run-fx/driver.mjs shot http://localhost:5000/fx/predictions /tmp/fx-predictions.png

# Click a selector after navigating
node /home/user/Legal-Work/.claude/skills/run-fx/driver.mjs click http://localhost:5000/fx/ 'a:has-text("Alerts")' /tmp/fx-alerts.png

# Screenshot with longer wait (1.5s after networkidle) + report JS errors and Chart.js instance state
node /home/user/Legal-Work/.claude/skills/run-fx/wait-shot.mjs http://localhost:5000/fx/ /tmp/fx-dashboard.png
```

`smoke` prints JSON like:

```json
{
  "summary": { "active_contracts": 3, "open_alerts": 0, ... },
  "dash":     { "title": "Dashboard - FX Recovery", "screenshot": "/tmp/fx-dashboard.png" },
  "contracts": { "url": ".../fx/contracts", "rows": 3 }
}
```

View the PNGs with the `Read` tool. **Always actually look at them** — `networkidle` can return before Chart.js paints the canvas. Use `wait-shot.mjs` (1.5s extra wait + Chart instance check) when chart rendering matters.

### Trigger interesting state via the API

```bash
# Re-fetch rates and re-evaluate thresholds (creates alerts when rates breach)
curl -s -X POST http://localhost:5000/fx/api/rates/refresh

# List current alerts
curl -s http://localhost:5000/fx/api/alerts | python -m json.tool

# Approve / dismiss an alert
curl -s -X POST http://localhost:5000/fx/api/alerts/<id>/approve -H 'Content-Type: application/json' -d '{"user":"agent"}'
```

The seed deliberately keeps base rates close to current mock rates — fresh databases usually produce `new_alerts: 0`. To force alerts, edit `fx.mock.sample_contracts` base rates downward before seeding, or shell into the DB and lower a clause's threshold.

### Run (human path)

```bash
FX_SCHEDULER_ENABLED=false python fx_app.py
# → open http://localhost:5000/fx/ in a browser on the same machine
```

Useful only on a workstation with a browser. Headless containers cannot do this — use the driver.

### Tests

```bash
python -m pytest -q                          # 45 unit tests, ~3s
python stress_tests/db_stress_test.py        # 5 DB concurrency tests, ~5s
```

There are also Locust HTTP tests in `stress_tests/locustfile.py` — use the `/fx-stress` slash command which orchestrates the full sequence (seed → launch → refresh → 60s 50-user run → cleanup).

### Stop

```bash
pkill -f "python fx_app.py"
```

## Gotchas

- **`pkill` from a `Bash` tool call kills the app you backgrounded in the same call.** A `nohup ... & disown` pattern is required; if you also `pkill` later in the same Bash invocation the tool harness will reap the new process. Put the launch in one Bash call, the verification curls in another.
- **Mock fallback is the default success path here, not a regression.** With `FX_FEED_SOURCE=mock` (the default) no live HTTP happens at all. With `FX_FEED_SOURCE=exchangerate_host` the live call reaches exchangerate.host but is rejected with `missing_access_key` (HTTP egress *does* work in this sandbox, contrary to a hint in CLAUDE.md — but the API requires a paid access key). Either way `monitoring/fx_feed.py` catches the exception, logs `falling back to mock`, and returns mock rates. Look for that exact substring in `/tmp/fx_app.log` to confirm the resilience path ran.
- **Chart.js is bundled locally** at `static/fx/js/chart.umd.js` + `chartjs-adapter-date-fns.bundle.min.js`. The base template loads them with `defer` so they run before `DOMContentLoaded`. This means screenshots in any environment (including this sandbox where outbound HTTPS to jsdelivr is blocked) render charts correctly — provided you wait long enough after page load (use `wait-shot.mjs` with its 1.5s extra wait).
- **Two static-url prefixes.** Templates load assets from `/fx/fx/static/...` (the blueprint's `static_url_path="/fx/static"` is itself nested under the `/fx` blueprint mount). That's correct; don't "fix" it.
- **The `/` route is the legacy Outlook-to-PDF converter, not FX.** Always navigate directly to `/fx/`. The two apps share the Flask process; they are unrelated per CLAUDE.md.
- **`fx_app.py` imports `app` at startup** to mount the legacy converter alongside FX. If the legacy converter's deps (weasyprint, RTFDE…) aren't installed, the import fails silently and `base_app` becomes a bare Flask. That's fine for driving `/fx/` — but the converter routes will 404.

## Troubleshooting

| Symptom | Cause / Fix |
|---|---|
| `ModuleNotFoundError: No module named 'flask'` on seed | Run the Prerequisites pip line. |
| `Cannot uninstall blinker 1.7.0, RECORD file not found` | Use `pip install --ignore-installed blinker ...` — the apt-packaged blinker has no pip metadata. |
| `ModuleNotFoundError: No module named 'reportlab'` on seed | `pip install --ignore-installed reportlab`. The seed renders sample contract PDFs. |
| `summary HTTP 000` after launching | The app died. Re-launch with `nohup ... & disown` (see Gotchas) and check `/tmp/fx_app.log`. |
| Screenshot is just the dark navbar with blank cards | Page errored. Curl `/fx/api/dashboard/summary` directly; check `/tmp/fx_app.log` for stack traces. |
| `chromium` complains about missing libs | `/opt/pw-browsers/chromium-1194/chrome-linux/chrome` is the only binary that works in this image; do not `npx playwright install` (writes to `~/.cache/ms-playwright` and downloads a different build). |
