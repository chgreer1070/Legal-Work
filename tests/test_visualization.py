"""
Unit and integration tests for the 3D contract visualization
(fx.routes.visualization): the build_graph() transformation, the
/api/contracts/graph endpoint, and the page route guard.
"""

from decimal import Decimal

import pytest
from flask import Flask

from fx import create_fx_blueprint
from fx.models import Alert, Contract, FXClause
from fx.routes.visualization import _excerpt, _risk_level, build_graph


# ── Fixtures & helpers ────────────────────────────────────────────────────────

@pytest.fixture
def client(test_db):
    """A Flask test client with the FX blueprint mounted on the isolated test DB."""
    app = Flask(__name__)
    app.register_blueprint(create_fx_blueprint(), url_prefix="/fx")
    app.config["TESTING"] = True
    return app.test_client()


def _make_contract(session, ref="C-1", customer="Acme", status="active"):
    c = Contract(customer_name=customer, contract_reference=ref, status=status)
    session.add(c)
    session.flush()
    return c


def _add_clause(session, contract_id, pair="USD/BRL", threshold="3.0",
                base="5.0", freq="monthly", method="full_passthrough",
                notice=30, text="", conf=0.9):
    cl = FXClause(
        contract_id=contract_id,
        currency_pair=pair,
        base_rate=Decimal(base),
        threshold_pct=Decimal(threshold),
        review_frequency=freq,
        adjustment_method=method,
        notification_period_days=notice,
        clause_text=text,
        confidence_score=conf,
    )
    session.add(cl)
    session.flush()
    return cl


def _add_alert(session, clause, status="triggered", exposure="1000", dev="4.0"):
    a = Alert(
        clause_id=clause.id,
        contract_id=clause.contract_id,
        currency_pair=clause.currency_pair,
        base_rate=clause.base_rate,
        current_rate=Decimal("5.25"),
        deviation_pct=Decimal(dev),
        exposure_amount=Decimal(exposure),
        status=status,
    )
    session.add(a)
    session.flush()
    return a


def _by_type(nodes):
    counts = {}
    for n in nodes:
        counts[n["type"]] = counts.get(n["type"], 0) + 1
    return counts


# ── _excerpt ──────────────────────────────────────────────────────────────────

def test_excerpt_empty_returns_empty():
    assert _excerpt(None) == ""
    assert _excerpt("") == ""


def test_excerpt_short_text_unchanged():
    assert _excerpt("short clause", limit=200) == "short clause"


def test_excerpt_long_text_truncated_with_ellipsis():
    text = "x" * 500
    out = _excerpt(text, limit=200)
    assert out.endswith("…")
    assert len(out) <= 201  # 200 chars + ellipsis


# ── _risk_level ───────────────────────────────────────────────────────────────

@pytest.mark.parametrize("alert_count,threshold,expected", [
    (0, 2.0, "high"),    # tight threshold
    (0, 3.0, "high"),    # boundary
    (1, 10.0, "high"),   # active alert overrides loose threshold
    (0, 4.0, "medium"),
    (0, 5.0, "medium"),  # boundary
    (0, 6.0, "low"),
])
def test_risk_level_classification(alert_count, threshold, expected):
    class _Clause:
        threshold_pct = Decimal(str(threshold))
    assert _risk_level(_Clause(), alert_count) == expected


# ── build_graph ───────────────────────────────────────────────────────────────

def test_build_graph_single_clause_node_and_link_counts(db_session):
    c = _make_contract(db_session)
    cl = _add_clause(db_session, c.id)
    db_session.commit()

    nodes, links = build_graph([c])
    counts = _by_type(nodes)

    # contract + clause + currency + ONE collapsed obligation
    assert counts == {"contract": 1, "clause": 1, "currency": 1, "obligation": 1}
    assert len(nodes) == 4
    # contains + monitors + requires
    assert len(links) == 3
    # obligation collapsed to a single node id
    oblig = [n for n in nodes if n["type"] == "obligation"]
    assert oblig[0]["id"] == f"oblig-{cl.id}"
    assert oblig[0]["details"]["adjustment_method"] == "full_passthrough"


def test_build_graph_dedupes_currency_pair_across_contracts(db_session):
    c1 = _make_contract(db_session, ref="C-1")
    c2 = _make_contract(db_session, ref="C-2")
    _add_clause(db_session, c1.id, pair="USD/BRL")
    _add_clause(db_session, c2.id, pair="USD/BRL")
    db_session.commit()

    nodes, links = build_graph([c1, c2])
    currency_nodes = [n for n in nodes if n["type"] == "currency"]

    # Shared currency pair => exactly one currency node bridging both contracts
    assert len(currency_nodes) == 1
    monitors = [l for l in links if l["type"] == "monitors"]
    assert len(monitors) == 2
    assert all(l["target"] == "pair-USD/BRL" for l in monitors)


def test_build_graph_clause_details_use_excerpt_not_full_text(db_session):
    c = _make_contract(db_session)
    long_text = "The parties agree that " + ("blah " * 100)
    _add_clause(db_session, c.id, text=long_text)
    db_session.commit()

    nodes, _ = build_graph([c])
    clause = [n for n in nodes if n["type"] == "clause"][0]

    assert "clause_text" not in clause["details"]
    assert "clause_excerpt" in clause["details"]
    assert clause["details"]["clause_excerpt"].endswith("…")
    assert clause["details"]["contract_id"] == c.id


def test_build_graph_creates_alert_and_exposure_nodes(db_session):
    c = _make_contract(db_session)
    cl = _add_clause(db_session, c.id)
    _add_alert(db_session, cl, exposure="5000")
    db_session.commit()

    nodes, links = build_graph([c])
    counts = _by_type(nodes)

    assert counts.get("alert") == 1
    assert counts.get("exposure") == 1
    assert any(l["type"] == "triggered" for l in links)
    assert any(l["type"] == "exposes" for l in links)


def test_build_graph_no_exposure_node_when_exposure_zero(db_session):
    c = _make_contract(db_session)
    cl = _add_clause(db_session, c.id)
    _add_alert(db_session, cl, exposure="0")
    db_session.commit()

    nodes, _ = build_graph([c])
    assert not any(n["type"] == "exposure" for n in nodes)


@pytest.mark.parametrize("exposure", ["1", "1000000", "10000000000"])
def test_build_graph_exposure_val_is_bounded(db_session, exposure):
    c = _make_contract(db_session)
    cl = _add_clause(db_session, c.id)
    _add_alert(db_session, cl, exposure=exposure)
    db_session.commit()

    nodes, _ = build_graph([c])
    exp = [n for n in nodes if n["type"] == "exposure"][0]
    # val = scaled*2, scaled in [2, 8]  =>  val in [4, 16]
    assert 4 <= exp["val"] <= 16


def test_build_graph_contract_with_no_clauses(db_session):
    c = _make_contract(db_session)
    db_session.commit()

    nodes, links = build_graph([c])
    assert len(nodes) == 1
    assert nodes[0]["type"] == "contract"
    assert nodes[0]["details"]["clause_count"] == 0
    assert links == []


def test_build_graph_empty_list():
    nodes, links = build_graph([])
    assert nodes == []
    assert links == []


# ── /api/contracts/graph ──────────────────────────────────────────────────────

def test_api_graph_single_contract_returns_shape(client, db_session):
    c = _make_contract(db_session)
    _add_clause(db_session, c.id)
    db_session.commit()

    resp = client.get(f"/fx/api/contracts/graph?contract_id={c.id}")
    assert resp.status_code == 200
    data = resp.get_json()
    assert set(["nodes", "links", "meta"]).issubset(data.keys())
    assert data["meta"]["contract_count"] == 1
    assert data["meta"]["node_count"] == len(data["nodes"])
    assert data["meta"]["truncated"] is False


def test_api_graph_all_contracts(client, db_session):
    c1 = _make_contract(db_session, ref="C-1")
    c2 = _make_contract(db_session, ref="C-2")
    _add_clause(db_session, c1.id, pair="USD/BRL")
    _add_clause(db_session, c2.id, pair="USD/MXN")
    db_session.commit()

    resp = client.get("/fx/api/contracts/graph")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["meta"]["contract_count"] == 2


def test_api_graph_excludes_inactive_contracts(client, db_session):
    active = _make_contract(db_session, ref="A-1", status="active")
    _make_contract(db_session, ref="P-1", status="pending_extraction")
    _add_clause(db_session, active.id)
    db_session.commit()

    resp = client.get("/fx/api/contracts/graph")
    data = resp.get_json()
    assert data["meta"]["contract_count"] == 1


def test_api_graph_404_for_missing_contract(client, db_session):
    resp = client.get("/fx/api/contracts/graph?contract_id=999")
    assert resp.status_code == 404
    assert "error" in resp.get_json()


def test_api_graph_contract_id_zero_is_single_lookup_not_all(client, db_session):
    # contract_id=0 must behave like a single (missing) contract -> 404,
    # mirroring the page route, not silently fall back to the all-contracts view.
    _make_contract(db_session, ref="C-1")
    db_session.commit()
    resp = client.get("/fx/api/contracts/graph?contract_id=0")
    assert resp.status_code == 404


def test_api_graph_meta_truncated_when_over_limit(client, db_session, monkeypatch):
    monkeypatch.setattr("fx.routes.visualization.MAX_GRAPH_CONTRACTS", 1)
    _make_contract(db_session, ref="C-1")
    _make_contract(db_session, ref="C-2")
    db_session.commit()

    resp = client.get("/fx/api/contracts/graph")
    data = resp.get_json()
    assert data["meta"]["truncated"] is True
    assert data["meta"]["contract_count"] == 1


# ── Page route guard ──────────────────────────────────────────────────────────

def test_page_route_all_contracts_renders(client, db_session):
    resp = client.get("/fx/contracts/3d")
    assert resp.status_code == 200
    assert b"contractId = null" in resp.data


def test_page_route_single_contract_renders(client, db_session):
    c = _make_contract(db_session)
    db_session.commit()
    resp = client.get(f"/fx/contracts/{c.id}/3d")
    assert resp.status_code == 200
    assert f"contractId = {c.id}".encode() in resp.data


def test_page_route_404_for_missing_contract(client, db_session):
    resp = client.get("/fx/contracts/999/3d")
    assert resp.status_code == 404
