---
description: Start the FX Recovery app locally (scheduler off) and show the dashboard URL
---

Start the FX Recovery app for manual inspection.

Steps:
1. Kill any existing `python fx_app.py` process
2. Reset the database (`rm -f fx_recovery.db*`) and re-seed with `python -m fx.mock.seed`
3. Start the app in the background with `FX_SCHEDULER_ENABLED=false python fx_app.py > /tmp/fx_app.log 2>&1 &`
4. Wait 2-3 seconds, then curl `http://localhost:5000/fx/api/dashboard/summary` to confirm it's up
5. Report:
   - The dashboard URL: `http://localhost:5000/fx/`
   - Active contracts / clauses / alerts from the summary
   - Reminder: localhost only works on the same machine (not a phone)
6. Tell the user how to trigger a rate refresh: `curl -X POST http://localhost:5000/fx/api/rates/refresh`

If the seed or app start fails, show the last 20 lines of `/tmp/fx_app.log` and stop. Do not loop-retry.
