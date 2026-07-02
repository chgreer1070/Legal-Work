"""
Tests for the /api/health endpoint.
"""

from datetime import datetime, timedelta
from decimal import Decimal

import pytest
from flask import Flask

from fx.models import FXRate
from fx.routes.api import api_bp


@pytest.fixture
def client(test_db):
    app = Flask(__name__)
    app.register_blueprint(api_bp)
    return app.test_client()


def test_health_ok_on_fresh_database(client):
    resp = client.get("/api/health")
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["status"] == "ok"
    assert body["checks"]["database"] == "ok"
    assert body["checks"]["extraction"] in ("claude_api", "rule_based")


def test_health_reports_rate_ages(client, db_session):
    db_session.add(
        FXRate(
            currency_pair="USD/BRL",
            rate=Decimal("5.10"),
            source="test",
            fetched_at=datetime.utcnow() - timedelta(minutes=5),
        )
    )
    db_session.commit()

    body = client.get("/api/health").get_json()
    assert "USD/BRL" in body["rate_age_minutes"]
    assert body["rate_age_minutes"]["USD/BRL"] == pytest.approx(5, abs=1.5)


def test_health_flags_stale_rates_when_scheduler_on(client, db_session, monkeypatch):
    monkeypatch.setenv("FX_SCHEDULER_ENABLED", "true")
    db_session.add(
        FXRate(
            currency_pair="USD/BRL",
            rate=Decimal("5.10"),
            source="test",
            fetched_at=datetime.utcnow() - timedelta(hours=6),
        )
    )
    db_session.commit()

    body = client.get("/api/health").get_json()
    assert body["checks"]["rates"] == "stale"
    assert body["status"] == "degraded"


def test_health_ignores_staleness_in_manual_mode(client, db_session, monkeypatch):
    monkeypatch.setenv("FX_SCHEDULER_ENABLED", "false")
    db_session.add(
        FXRate(
            currency_pair="USD/BRL",
            rate=Decimal("5.10"),
            source="test",
            fetched_at=datetime.utcnow() - timedelta(hours=6),
        )
    )
    db_session.commit()

    body = client.get("/api/health").get_json()
    assert body["checks"]["rates"] == "ok"
    assert body["status"] == "ok"
