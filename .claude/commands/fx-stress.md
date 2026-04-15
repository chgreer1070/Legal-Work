---
description: Run the full FX stress test suite (DB concurrency + HTTP load test)
---

Run the full stress test suite for the FX Recovery System.

Steps:
1. Run the DB/logic stress test (no HTTP): `python stress_tests/db_stress_test.py`
   - All 5 tests should pass. Report per-test timings.
2. Reset and seed a fresh DB: `rm -f fx_recovery.db* && python -m fx.mock.seed`
3. Start the app in the background: `FX_SCHEDULER_ENABLED=false python fx_app.py > /tmp/fx_app.log 2>&1 &`
4. Wait ~3 seconds; confirm `/fx/api/dashboard/summary` responds with 200
5. Trigger one rate refresh so there are alerts to exercise: `curl -s -X POST http://localhost:5000/fx/api/rates/refresh > /dev/null`
6. Run Locust in headless mode: `locust -f stress_tests/locustfile.py --host=http://localhost:5000 --headless -u 50 -r 10 -t 60s`
7. Kill the background app: `pkill -f "python fx_app.py"` (ignore errors)
8. Report to the user in a compact table:
   - Total requests, failure %, throughput (req/s)
   - p50, p95, p99, max response times
   - Any endpoint with > 500ms p95 (flag as a concern)
9. Clean up any leftover `stress_test.db*` files so the Stop hook doesn't nag

If any step fails, stop immediately and show the error. Do not retry blindly.
