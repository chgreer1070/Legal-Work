"""
APScheduler wrapper for periodic rate fetching and threshold checking.
"""

from apscheduler.schedulers.background import BackgroundScheduler

from fx.config import RATE_FETCH_INTERVAL_MINUTES, THRESHOLD_CHECK_INTERVAL_MINUTES

_scheduler = None


def _fetch_rates_job():
    """Background job: fetch and cache current FX rates."""
    try:
        from fx.monitoring.rate_cache import refresh_rates
        refresh_rates()
    except Exception as e:
        print(f"[FX Scheduler] Rate fetch error: {e}")


def _check_thresholds_job():
    """Background job: check all thresholds against current rates."""
    try:
        from fx.monitoring.threshold_checker import check_all_thresholds
        alerts = check_all_thresholds()
        if alerts:
            print(f"[FX Scheduler] {len(alerts)} new alerts triggered")
    except Exception as e:
        print(f"[FX Scheduler] Threshold check error: {e}")


def start_scheduler(app=None):
    """Start the background scheduler for rate monitoring."""
    global _scheduler
    if _scheduler is not None:
        return

    _scheduler = BackgroundScheduler()
    _scheduler.add_job(
        _fetch_rates_job,
        "interval",
        minutes=RATE_FETCH_INTERVAL_MINUTES,
        id="fx_rate_fetch",
        replace_existing=True,
    )
    _scheduler.add_job(
        _check_thresholds_job,
        "interval",
        minutes=THRESHOLD_CHECK_INTERVAL_MINUTES,
        id="fx_threshold_check",
        replace_existing=True,
    )
    _scheduler.start()
    print(f"[FX Scheduler] Started: rates every {RATE_FETCH_INTERVAL_MINUTES}min, thresholds every {THRESHOLD_CHECK_INTERVAL_MINUTES}min")


def stop_scheduler():
    """Stop the background scheduler."""
    global _scheduler
    if _scheduler:
        _scheduler.shutdown()
        _scheduler = None
