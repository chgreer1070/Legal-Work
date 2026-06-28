"""
Tests for the shared route helper fx.routes.util.get_or_404.
"""

import pytest
from flask import Flask
from werkzeug.exceptions import HTTPException

from fx.db import get_session
from fx.models import Contract
from fx.routes.util import get_or_404


@pytest.fixture
def app_ctx(test_db):
    """An application context so jsonify() works inside the helper."""
    app = Flask(__name__)
    with app.app_context():
        yield app


def test_get_or_404_returns_object_when_found(app_ctx, db_session):
    c = Contract(customer_name="Acme", contract_reference="R-1", status="active")
    db_session.add(c)
    db_session.commit()

    session = get_session()
    try:
        obj = get_or_404(session, Contract, c.id, "Contract")
        assert obj.id == c.id
    finally:
        session.close()


def test_get_or_404_json_aborts_with_404(app_ctx):
    session = get_session()
    try:
        with pytest.raises(HTTPException) as exc:
            get_or_404(session, Contract, 999, "Contract")
        # abort(Response) carries the status on the wrapped response, not on
        # HTTPException.code (which is None for a custom-response abort).
        response = exc.value.get_response()
        assert response.status_code == 404
        assert response.get_json() == {"error": "Contract not found"}
    finally:
        session.close()


def test_get_or_404_html_aborts_with_plain_404(app_ctx):
    session = get_session()
    try:
        with pytest.raises(HTTPException) as exc:
            get_or_404(session, Contract, 999, "Contract", as_json=False)
        assert exc.value.code == 404
    finally:
        session.close()
