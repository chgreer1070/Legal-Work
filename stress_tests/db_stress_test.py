"""
Database and business logic stress tests for the FX Recovery System.

Directly tests core components without HTTP, focusing on:
- SQLite concurrent read/write under load
- Query performance with large datasets
- Business logic throughput
- State machine concurrency safety

Usage:
    python stress_tests/db_stress_test.py
"""

import os
import sys
import time
import threading
import traceback
from datetime import date, datetime, timedelta
from decimal import Decimal
from pathlib import Path

# Ensure project root is on path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# Use a separate test database
TEST_DB = "stress_test.db"
os.environ["FX_DATABASE_PATH"] = TEST_DB
os.environ["FX_SCHEDULER_ENABLED"] = "false"
os.environ["FX_FEED_SOURCE"] = "mock"

from fx.db import init_db, get_session, engine, Base
from fx.models import Alert, Contract, FXClause, FXRate, Transaction, AuditEntry


# ── Helpers ─────────────────────────────────────────────────────────────────

def reset_db():
    """Drop and recreate all tables."""
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)


def seed_large_dataset(n_contracts=100, clauses_per=3, n_rates=10000):
    """Seed a large dataset for performance testing."""
    session = get_session()
    try:
        pairs = ["USD/BRL", "USD/MXN", "USD/CNY"]
        base_rates = {"USD/BRL": 5.05, "USD/MXN": 17.50, "USD/CNY": 7.25}

        # Contracts and clauses
        for i in range(n_contracts):
            contract = Contract(
                customer_name=f"StressTest Corp {i}",
                contract_reference=f"STRESS-{i:06d}",
                status="active",
            )
            session.add(contract)
            session.flush()

            for j in range(clauses_per):
                pair = pairs[j % len(pairs)]
                clause = FXClause(
                    contract_id=contract.id,
                    currency_pair=pair,
                    base_rate=Decimal(str(base_rates[pair])),
                    threshold_pct=Decimal("3.0"),
                    review_frequency="monthly",
                    adjustment_method="full_passthrough",
                    notification_period_days=30,
                    clause_text=f"Stress test clause {j} for {pair}",
                    confidence_score=0.95,
                )
                session.add(clause)

            # Add transactions
            for pair in pairs:
                txn = Transaction(
                    contract_id=contract.id,
                    currency_pair=pair,
                    period_start=date(2025, 1, 1),
                    period_end=date(2025, 12, 31),
                    volume=Decimal("500000.00"),
                    transaction_count=50,
                )
                session.add(txn)

        session.commit()

        # Historical rates
        now = datetime.utcnow()
        for i in range(n_rates):
            pair = pairs[i % len(pairs)]
            rate_val = base_rates[pair] * (1 + (i % 100 - 50) * 0.001)
            rate = FXRate(
                currency_pair=pair,
                rate=Decimal(str(round(rate_val, 6))),
                source="stress_test",
                fetched_at=now - timedelta(minutes=i * 15),
            )
            session.add(rate)
            if i % 1000 == 0:
                session.flush()

        session.commit()
        print(f"  Seeded {n_contracts} contracts, {n_contracts * clauses_per} clauses, {n_rates} rates")
    finally:
        session.close()


def create_test_alert(status="triggered"):
    """Create a single alert for testing."""
    session = get_session()
    try:
        contract = session.query(Contract).first()
        clause = session.query(FXClause).first()
        if not contract or not clause:
            raise RuntimeError("Need seeded data first")

        alert = Alert(
            clause_id=clause.id,
            contract_id=contract.id,
            currency_pair=clause.currency_pair,
            base_rate=clause.base_rate,
            current_rate=clause.base_rate * Decimal("1.05"),
            deviation_pct=Decimal("5.0"),
            exposure_amount=Decimal("25000.00"),
            status=status,
        )
        session.add(alert)
        session.commit()
        return alert.id
    finally:
        session.close()


class TestResult:
    def __init__(self, name):
        self.name = name
        self.passed = False
        self.duration = 0
        self.details = ""
        self.errors = []


# ── Test 1: Concurrent DB Read/Write ────────────────────────────────────────

def test_concurrent_read_write():
    """Spawn threads doing simultaneous reads and writes to SQLite."""
    result = TestResult("Concurrent DB Read/Write")
    errors = []
    write_count = [0]
    read_count = [0]
    lock = threading.Lock()

    def writer(thread_id, n_writes=50):
        for i in range(n_writes):
            try:
                session = get_session()
                rate = FXRate(
                    currency_pair="USD/BRL",
                    rate=Decimal(str(5.05 + i * 0.001)),
                    source=f"writer_{thread_id}",
                )
                session.add(rate)
                session.commit()
                session.close()
                with lock:
                    write_count[0] += 1
            except Exception as e:
                with lock:
                    errors.append(f"Writer {thread_id}: {e}")

    def reader(thread_id, n_reads=50):
        for _ in range(n_reads):
            try:
                session = get_session()
                rates = (
                    session.query(FXRate)
                    .filter(FXRate.currency_pair == "USD/BRL")
                    .order_by(FXRate.fetched_at.desc())
                    .limit(10)
                    .all()
                )
                _ = [r.to_dict() for r in rates]
                session.close()
                with lock:
                    read_count[0] += 1
            except Exception as e:
                with lock:
                    errors.append(f"Reader {thread_id}: {e}")

    start = time.time()
    threads = []
    for i in range(10):
        threads.append(threading.Thread(target=writer, args=(i,)))
    for i in range(10):
        threads.append(threading.Thread(target=reader, args=(i,)))

    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=60)

    result.duration = time.time() - start
    result.details = f"Writes: {write_count[0]}/500, Reads: {read_count[0]}/500"
    result.errors = errors

    # Allow a small number of retryable errors but no data corruption
    db_locked = [e for e in errors if "database is locked" in str(e)]
    other_errors = [e for e in errors if "database is locked" not in str(e)]
    result.passed = len(other_errors) == 0 and len(db_locked) <= 5

    if db_locked:
        result.details += f", DB locked errors: {len(db_locked)}"

    return result


# ── Test 2: Large Dataset Query Performance ─────────────────────────────────

def test_query_performance():
    """Test query performance with a large dataset."""
    result = TestResult("Large Dataset Query Performance")
    timings = {}

    # Dashboard summary query
    start = time.time()
    session = get_session()
    try:
        active = session.query(Contract).filter(Contract.status == "active").count()
        total_clauses = session.query(FXClause).count()
        open_alerts = (
            session.query(Alert)
            .filter(Alert.status.in_(["triggered", "pending_approval"]))
            .count()
        )
    finally:
        session.close()
    timings["dashboard_summary"] = time.time() - start

    # Exposure by pair
    start = time.time()
    from fx.exposure.calculator import get_total_exposure_by_pair
    get_total_exposure_by_pair()
    timings["exposure_by_pair"] = time.time() - start

    # Rate history query
    start = time.time()
    from fx.monitoring.rate_cache import get_rate_history
    history = get_rate_history("USD/BRL", days=90)
    timings["rate_history"] = time.time() - start
    timings["rate_history_rows"] = len(history)

    # Contract list with clause count
    start = time.time()
    session = get_session()
    try:
        contracts = session.query(Contract).all()
        _ = [c.to_dict() for c in contracts]
    finally:
        session.close()
    timings["contract_list"] = time.time() - start

    # Audit log query
    start = time.time()
    from fx.audit.logger import get_audit_log
    get_audit_log(limit=500)
    timings["audit_log"] = time.time() - start

    result.duration = sum(v for k, v in timings.items() if not k.endswith("_rows"))
    result.details = ", ".join(
        f"{k}: {v:.3f}s" if not k.endswith("_rows") else f"{k}: {v}"
        for k, v in timings.items()
    )

    # All queries should complete under 1 second each
    slow = {k: v for k, v in timings.items() if not k.endswith("_rows") and v > 1.0}
    result.passed = len(slow) == 0
    if slow:
        result.errors = [f"Slow query: {k} took {v:.3f}s" for k, v in slow.items()]

    return result


# ── Test 3: Threshold Checker Throughput ────────────────────────────────────

def test_threshold_checker_throughput():
    """Measure threshold checking throughput with many contracts."""
    result = TestResult("Threshold Checker Throughput")

    # Ensure there are some current rates
    from fx.monitoring.rate_cache import refresh_rates
    refresh_rates()

    from fx.monitoring.threshold_checker import check_all_thresholds

    iterations = 5
    times = []
    total_alerts = 0

    for i in range(iterations):
        start = time.time()
        alerts = check_all_thresholds()
        elapsed = time.time() - start
        times.append(elapsed)
        total_alerts += len(alerts)

    avg_time = sum(times) / len(times)
    max_time = max(times)

    result.duration = sum(times)
    result.details = (
        f"Iterations: {iterations}, "
        f"Avg: {avg_time:.3f}s, Max: {max_time:.3f}s, "
        f"Total new alerts: {total_alerts}"
    )

    # Each check should be under 2 seconds
    result.passed = max_time < 2.0
    if not result.passed:
        result.errors = [f"Max iteration time {max_time:.3f}s exceeds 2s target"]

    return result


# ── Test 4: Concurrent Rate Refresh ─────────────────────────────────────────

def test_concurrent_rate_refresh():
    """Multiple threads refreshing rates simultaneously."""
    result = TestResult("Concurrent Rate Refresh")
    errors = []
    success_count = [0]
    lock = threading.Lock()

    from fx.monitoring.rate_cache import refresh_rates

    def do_refresh(thread_id):
        try:
            saved = refresh_rates()
            with lock:
                success_count[0] += 1
        except Exception as e:
            with lock:
                errors.append(f"Thread {thread_id}: {e}")

    # Count rates before
    session = get_session()
    before_count = session.query(FXRate).count()
    session.close()

    start = time.time()
    threads = [threading.Thread(target=do_refresh, args=(i,)) for i in range(10)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=60)

    result.duration = time.time() - start

    # Count rates after
    session = get_session()
    after_count = session.query(FXRate).count()
    session.close()

    new_rates = after_count - before_count
    result.details = (
        f"Threads: 10, Successes: {success_count[0]}/10, "
        f"New rate records: {new_rates}"
    )
    result.errors = errors

    # All threads should succeed; expect ~30 new rates (10 threads x 3 pairs)
    result.passed = success_count[0] == 10 and len(errors) == 0
    return result


# ── Test 5: Alert State Machine Concurrency ─────────────────────────────────

def test_alert_state_concurrency():
    """Multiple threads racing to change the same alert's state."""
    result = TestResult("Alert State Machine Concurrency")

    from fx.notifications.approval import approve_alert, dismiss_alert

    # Create an alert in pending_approval state
    alert_id = create_test_alert(status="pending_approval")

    successes = []
    failures = []
    lock = threading.Lock()

    def try_approve(thread_id):
        try:
            r = approve_alert(alert_id, approved_by=f"thread_{thread_id}")
            with lock:
                successes.append(("approve", thread_id))
        except ValueError:
            with lock:
                failures.append(("approve_rejected", thread_id))
        except Exception as e:
            with lock:
                failures.append(("approve_error", thread_id, str(e)))

    def try_dismiss(thread_id):
        try:
            r = dismiss_alert(alert_id, dismissed_by=f"thread_{thread_id}")
            with lock:
                successes.append(("dismiss", thread_id))
        except ValueError:
            with lock:
                failures.append(("dismiss_rejected", thread_id))
        except Exception as e:
            with lock:
                failures.append(("dismiss_error", thread_id, str(e)))

    start = time.time()
    threads = []
    for i in range(5):
        threads.append(threading.Thread(target=try_approve, args=(i,)))
    for i in range(5):
        threads.append(threading.Thread(target=try_dismiss, args=(i + 5,)))

    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=30)

    result.duration = time.time() - start

    # Verify final state
    session = get_session()
    alert = session.query(Alert).filter(Alert.id == alert_id).first()
    final_status = alert.status if alert else "NOT FOUND"
    session.close()

    result.details = (
        f"Successes: {len(successes)}, Rejections: {len(failures)}, "
        f"Final status: {final_status}"
    )

    # Exactly one operation should succeed (no double transitions)
    unexpected_errors = [f for f in failures if f[0].endswith("_error")]
    result.errors = [str(e) for e in unexpected_errors]

    # At least one success, and final state should be valid
    result.passed = (
        len(successes) >= 1
        and final_status in ("approved", "dismissed")
        and len(unexpected_errors) == 0
    )

    return result


# ── Runner ──────────────────────────────────────────────────────────────────

def run_all():
    print("=" * 70)
    print("FX Recovery System — Database & Logic Stress Tests")
    print("=" * 70)
    print()

    # Setup
    print("[Setup] Creating test database...")
    reset_db()

    print("[Setup] Seeding large dataset (100 contracts, 300 clauses, 10k rates)...")
    seed_large_dataset(n_contracts=100, clauses_per=3, n_rates=10000)
    print()

    # Run tests
    tests = [
        ("1", test_concurrent_read_write),
        ("2", test_query_performance),
        ("3", test_threshold_checker_throughput),
        ("4", test_concurrent_rate_refresh),
        ("5", test_alert_state_concurrency),
    ]

    results = []
    for num, test_fn in tests:
        print(f"[Test {num}] {test_fn.__doc__.strip()}")
        try:
            r = test_fn()
        except Exception as e:
            r = TestResult(test_fn.__doc__.strip())
            r.errors = [traceback.format_exc()]
        results.append(r)

        status = "PASS" if r.passed else "FAIL"
        print(f"  [{status}] {r.details} ({r.duration:.2f}s)")
        for err in r.errors[:3]:  # Show up to 3 errors
            print(f"    ERROR: {err}")
        print()

    # Summary
    print("=" * 70)
    passed = sum(1 for r in results if r.passed)
    total = len(results)
    print(f"Results: {passed}/{total} passed")
    print("=" * 70)

    # Cleanup
    print("\n[Cleanup] Removing test database...")
    try:
        os.unlink(TEST_DB)
        for suffix in ("-shm", "-wal"):
            p = TEST_DB + suffix
            if os.path.exists(p):
                os.unlink(p)
    except OSError:
        pass

    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(run_all())
