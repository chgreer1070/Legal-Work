"""
Contract management routes.
"""

import logging
from pathlib import Path

from flask import Blueprint, jsonify, render_template, request
from werkzeug.utils import secure_filename

from fx.config import CONTRACT_UPLOAD_DIR
from fx.db import get_session
from fx.models import Contract, FXClause
from fx.audit.logger import log_event
from fx.exposure.formula import FormulaError, validate_formula

ALLOWED_EXTENSIONS = {".pdf", ".docx", ".doc"}

logger = logging.getLogger(__name__)

contracts_bp = Blueprint("fx_contracts", __name__)


def _persist_clauses(session, contract, clause_schemas):
    """Create FXClause rows from extracted clause schemas, validating formulas."""
    for clause_data in clause_schemas:
        expression = (clause_data.formula_expression or "").strip()
        if expression:
            try:
                validate_formula(expression)
            except FormulaError as e:
                logger.warning(
                    "Rejecting invalid formula for %s on contract %d (%r): %s",
                    clause_data.currency_pair, contract.id, expression, e,
                )
                expression = ""
        session.add(FXClause(
            contract_id=contract.id,
            currency_pair=clause_data.currency_pair,
            base_rate=clause_data.base_rate,
            threshold_pct=clause_data.threshold_pct,
            review_frequency=clause_data.review_frequency,
            adjustment_method=clause_data.adjustment_method,
            notification_period_days=clause_data.notification_period_days,
            clause_text=clause_data.clause_text,
            formula_type=clause_data.formula_type,
            formula_expression=expression,
            formula_description=clause_data.formula_description,
            confidence_score=clause_data.confidence_score,
        ))


def _start_tracking(contract_id, clause_schemas) -> int:
    """
    Begin exposure tracking for freshly extracted clauses: generate
    transaction history, refresh rates, and run an immediate threshold
    check. Returns the number of new alerts created.
    """
    from fx.exposure.transaction_data import generate_mock_transactions
    from fx.monitoring.rate_cache import refresh_rates
    from fx.monitoring.threshold_checker import check_all_thresholds

    for clause_data in clause_schemas:
        generate_mock_transactions(contract_id, clause_data.currency_pair)

    try:
        refresh_rates()
        return len(check_all_thresholds())
    except Exception as e:
        # Tracking continues on the scheduler's next cycle — never fail the upload
        logger.error("Immediate threshold check failed for contract %d: %s", contract_id, e)
        return 0


@contracts_bp.route("/contracts")
def list_contracts():
    """Contract list page."""
    return render_template("contracts.html")


@contracts_bp.route("/contracts/<int:contract_id>")
def contract_detail(contract_id: int):
    """Contract detail page."""
    return render_template("contract_detail.html", contract_id=contract_id)


@contracts_bp.route("/api/contracts", methods=["GET"])
def api_list_contracts():
    """JSON list of contracts."""
    session = get_session()
    try:
        contracts = session.query(Contract).order_by(Contract.created_at.desc()).all()
        return jsonify([c.to_dict() for c in contracts])
    finally:
        session.close()


@contracts_bp.route("/api/contracts/<int:contract_id>", methods=["GET"])
def api_contract_detail(contract_id: int):
    """JSON contract detail with clauses."""
    session = get_session()
    try:
        contract = session.query(Contract).filter(Contract.id == contract_id).first()
        if not contract:
            return jsonify({"error": "Contract not found"}), 404

        data = contract.to_dict()
        data["clauses"] = [c.to_dict() for c in contract.clauses]
        return jsonify(data)
    finally:
        session.close()


@contracts_bp.route("/contracts/upload", methods=["POST"])
def upload_contract():
    """Upload a contract file and trigger ingestion."""
    if "file" not in request.files:
        return jsonify({"error": "No file provided"}), 400

    file = request.files["file"]
    if not file.filename:
        return jsonify({"error": "No file selected"}), 400

    # Validate file extension
    filename = secure_filename(file.filename)
    if not filename:
        return jsonify({"error": "Invalid filename"}), 400

    ext = Path(filename).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        return jsonify({"error": f"Unsupported file type: {ext}. Allowed: {', '.join(ALLOWED_EXTENSIONS)}"}), 400

    customer_name = request.form.get("customer_name", "Unknown Customer")[:255]
    contract_ref = request.form.get("contract_reference", "")[:100]

    if not contract_ref:
        import uuid
        contract_ref = f"FX-{uuid.uuid4().hex[:8].upper()}"

    # Save uploaded file with sanitized filename
    upload_dir = Path(CONTRACT_UPLOAD_DIR)
    upload_dir.mkdir(parents=True, exist_ok=True)
    file_path = upload_dir / filename
    file.save(str(file_path))

    session = get_session()
    try:
        # Create contract record
        contract = Contract(
            customer_name=customer_name,
            contract_reference=contract_ref,
            file_path=str(file_path),
            status="pending_extraction",
        )
        session.add(contract)
        session.commit()

        log_event(
            event_type="contract_uploaded",
            entity_type="contract",
            entity_id=contract.id,
            action=f"Contract uploaded: {file.filename}",
            details={"filename": file.filename, "customer": customer_name},
        )

        # Extract text
        try:
            from fx.ingestion.parser import extract_text
            raw_text = extract_text(file_path)
            contract.raw_text = raw_text
            session.commit()
        except Exception as e:
            contract.status = "extraction_failed"
            session.commit()
            return jsonify({
                "error": f"Text extraction failed: {str(e)}",
                "contract_id": contract.id,
            }), 422

        # Extract clauses via Claude API
        try:
            from fx.ingestion.clause_extractor import extract_clauses
            result = extract_clauses(raw_text, contract_id=contract.id)
            _persist_clauses(session, contract, result.clauses)

            contract.status = "active"
            session.commit()

            # Begin exposure tracking immediately
            new_alerts = _start_tracking(contract.id, result.clauses)

            return jsonify({
                "contract_id": contract.id,
                "clauses_extracted": len(result.clauses),
                "new_alerts": new_alerts,
                "status": "active",
            })
        except Exception as e:
            contract.status = "active"  # Still active, just no auto-extraction
            session.commit()
            return jsonify({
                "contract_id": contract.id,
                "clauses_extracted": 0,
                "warning": f"Claude extraction unavailable: {str(e)}",
                "status": "active",
            })
    finally:
        session.close()


@contracts_bp.route("/contracts/<int:contract_id>/re-extract", methods=["POST"])
def re_extract_clauses(contract_id: int):
    """Re-run clause extraction for a contract."""
    session = get_session()
    try:
        contract = session.query(Contract).filter(Contract.id == contract_id).first()
        if not contract:
            return jsonify({"error": "Contract not found"}), 404

        if not contract.raw_text:
            return jsonify({"error": "No text available for extraction"}), 422

        # Remove existing clauses
        session.query(FXClause).filter(FXClause.contract_id == contract_id).delete()
        session.commit()

        try:
            from fx.ingestion.clause_extractor import extract_clauses
            result = extract_clauses(contract.raw_text, contract_id=contract_id)
            _persist_clauses(session, contract, result.clauses)
            session.commit()

            # Begin exposure tracking immediately
            new_alerts = _start_tracking(contract.id, result.clauses)

            return jsonify({
                "contract_id": contract_id,
                "clauses_extracted": len(result.clauses),
                "new_alerts": new_alerts,
            })
        except Exception as e:
            return jsonify({"error": f"Extraction failed: {str(e)}"}), 500
    finally:
        session.close()
