---
description: Kill the FX app, wipe the database, and re-seed with fresh mock data
---

Reset the FX Recovery database to a clean seeded state.

Steps:
1. Kill any running `python fx_app.py` process (best-effort; ignore errors)
2. `rm -f fx_recovery.db fx_recovery.db-shm fx_recovery.db-wal`
3. Also remove `stress_test.db*` if it exists
4. Run `python -m fx.mock.seed`
5. Show the seed output (3 contracts, 4 clauses, 90 days of rates)
6. Report that the DB is clean and ready. Do NOT start the app — that's what `/fx-run` is for.
