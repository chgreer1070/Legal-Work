# Stress Tests

## Setup

```bash
pip install locust
```

## DB & Logic Stress Test (no server needed)

```bash
python stress_tests/db_stress_test.py
```

Tests concurrent SQLite read/write, query performance with large datasets,
threshold checker throughput, concurrent rate refresh, and alert state machine races.

## HTTP Load Test (Locust)

```bash
# 1. Start the app (scheduler disabled to avoid interference)
FX_SCHEDULER_ENABLED=false python fx_app.py &

# 2a. Web UI mode (open http://localhost:8089)
locust -f stress_tests/locustfile.py --host=http://localhost:5000

# 2b. Headless mode
locust -f stress_tests/locustfile.py --host=http://localhost:5000 \
    --headless -u 50 -r 5 -t 3m
```

### What to look for

- **p95 response time**: Read endpoints should be < 500ms, write < 2s
- **Failure rate**: Should be 0% for read endpoints
- **SQLite locking**: Check app logs for "database is locked" errors under write load
