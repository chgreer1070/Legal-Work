"""
Shared helpers for the FX route blueprints.
"""

from flask import abort, jsonify


def get_or_404(session, model, entity_id, label="Resource", as_json=True):
    """Fetch a row by primary key, or abort with 404.

    Centralizes the fetch-or-404 pattern that was duplicated across the
    contract, alert, and visualization blueprints. JSON API routes get a
    ``{"error": "<label> not found"}`` body; page routes (``as_json=False``)
    get Flask's default HTML 404.

    Aborting (rather than returning) lets callers write a single assignment
    and keeps any surrounding ``try/finally`` session cleanup intact, since
    the raised HTTPException still unwinds through ``finally``.
    """
    obj = session.get(model, entity_id)
    if obj is None:
        if as_json:
            response = jsonify({"error": f"{label} not found"})
            response.status_code = 404
            abort(response)
        abort(404)
    return obj
