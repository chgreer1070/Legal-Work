"""
SOX-compliant audit trail logging.
"""

import hashlib
import json

from fx.db import get_session
from fx.models import AuditEntry


def log_event(
    event_type: str,
    entity_type: str,
    entity_id: int | None,
    action: str,
    actor: str = "system",
    details: dict | None = None,
    ai_model_used: str | None = None,
    ai_prompt: str | None = None,
    ai_response: str | None = None,
    session=None,
):
    """Record an audit entry with optional AI provenance hashes."""
    entry = AuditEntry(
        event_type=event_type,
        entity_type=entity_type,
        entity_id=entity_id,
        actor=actor,
        action=action,
        details=json.dumps(details) if details else None,
        ai_model_used=ai_model_used,
        ai_prompt_hash=hashlib.sha256(ai_prompt.encode()).hexdigest() if ai_prompt else None,
        ai_response_hash=hashlib.sha256(ai_response.encode()).hexdigest() if ai_response else None,
    )
    owns_session = session is None
    if owns_session:
        session = get_session()
    try:
        session.add(entry)
        if owns_session:
            session.commit()
    finally:
        if owns_session:
            session.close()


def get_audit_log(entity_type: str | None = None, entity_id: int | None = None, limit: int = 100):
    """Retrieve audit entries with optional filtering."""
    session = get_session()
    try:
        query = session.query(AuditEntry).order_by(AuditEntry.timestamp.desc())
        if entity_type:
            query = query.filter(AuditEntry.entity_type == entity_type)
        if entity_id:
            query = query.filter(AuditEntry.entity_id == entity_id)
        return [e.to_dict() for e in query.limit(limit).all()]
    finally:
        session.close()
