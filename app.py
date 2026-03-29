"""
Legal-Work – Flask web application.

Routes
------
GET  /              Drag-and-drop upload page (Outlook-to-PDF converter)
POST /convert       Accept uploaded files, run conversion, return JSON status
GET  /download/<id> Download a converted output bundle (zip)
GET  /jobs          List recent conversion jobs (JSON)

GET  /contracttwin       ContractTwin 3D visualization page
GET  /contracttwin/demo  Pre-parsed demo EMS contract (JSON)
POST /contracttwin/parse Parse uploaded/pasted contract text (JSON)
GET  /contracttwin/scenarios/<id>  Run scenario simulation (JSON)
"""

import json
import os
import shutil
import tempfile
import threading
import uuid
import zipfile
from datetime import datetime
from pathlib import Path

from flask import (
    Flask,
    jsonify,
    render_template,
    request,
    send_file,
    url_for,
)

from converter import convert_standalone, msg_to_pdf

# ContractTwin imports
from contract_parser import parse_contract
from demo_contract import get_demo_contract
from graph_builder import build_graph
from plain_english import translate_clause
from economics_engine import (
    compute_clause_economics,
    compute_interaction_effects,
    compute_portfolio_summary,
    compute_time_profile,
    generate_recommendations,
    monte_carlo_simulation,
)
from scenario_engine import get_all_scenario_summaries, run_scenario, SCENARIOS
from ems_ontology import ZONES

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 200 * 1024 * 1024  # 200 MB

UPLOAD_DIR  = Path("uploads")
OUTPUT_DIR  = Path("output")
ALLOWED_EXT = {".msg", ".pdf", ".doc", ".docx", ".ppt", ".pptx"}

# In-memory job store: { job_id: { status, message, files, created_at } }
_jobs: dict[str, dict] = {}
_jobs_lock = threading.Lock()


# ── helpers ──────────────────────────────────────────────────────────────────

def _allowed(filename: str) -> bool:
    return Path(filename).suffix.lower() in ALLOWED_EXT


def _job_output_dir(job_id: str) -> Path:
    return OUTPUT_DIR / job_id


def _run_conversion(job_id: str, upload_paths: list[Path]):
    """Background thread: convert all uploaded files and update job state."""
    out_dir = _job_output_dir(job_id)
    out_dir.mkdir(parents=True, exist_ok=True)

    results = []
    errors  = []

    # Sort: process .msg files first so their attachments can be paired
    msg_files   = [p for p in upload_paths if p.suffix.lower() == ".msg"]
    other_files = [p for p in upload_paths if p.suffix.lower() != ".msg"]

    for msg_path in msg_files:
        try:
            # Each email gets its own sub-folder
            email_slug = msg_path.stem[:50].strip()
            email_dir  = out_dir / email_slug
            email_dir.mkdir(exist_ok=True)

            result = msg_to_pdf(msg_path, email_dir)

            entry = {
                "type":        "email",
                "source":      msg_path.name,
                "email_pdf":   str(result["email_pdf"].relative_to(out_dir)),
                "attachments": [
                    str(p.relative_to(out_dir))
                    for p in result["attachments"]
                ],
                "subject":     result["metadata"].get("title", ""),
                "from":        result["metadata"].get("from", ""),
                "date":        result["metadata"].get("date_str", ""),
            }
            results.append(entry)
        except Exception as exc:
            errors.append({"file": msg_path.name, "error": str(exc)})

    for src_path in other_files:
        try:
            pdf = convert_standalone(src_path, out_dir)
            if pdf:
                results.append({
                    "type":   "document",
                    "source": src_path.name,
                    "pdf":    str(pdf.relative_to(out_dir)),
                })
            else:
                errors.append({"file": src_path.name, "error": "Conversion failed"})
        except Exception as exc:
            errors.append({"file": src_path.name, "error": str(exc)})

    # Cleanup uploads
    for p in upload_paths:
        p.unlink(missing_ok=True)

    with _jobs_lock:
        _jobs[job_id]["status"]  = "done" if not errors else "done_with_errors"
        _jobs[job_id]["results"] = results
        _jobs[job_id]["errors"]  = errors


# ── routes ───────────────────────────────────────────────────────────────────

@app.route("/")
def index():
    return render_template("index.html")


@app.route("/dashboard")
def dashboard():
    return render_template("dashboard.html")


@app.route("/convert", methods=["POST"])
def convert():
    if "files" not in request.files:
        return jsonify({"error": "No files provided"}), 400

    files = request.files.getlist("files")
    if not files:
        return jsonify({"error": "No files selected"}), 400

    job_id    = str(uuid.uuid4())
    job_dir   = UPLOAD_DIR / job_id
    job_dir.mkdir(parents=True, exist_ok=True)

    saved: list[Path] = []
    rejected: list[str] = []

    for f in files:
        if not f.filename:
            continue
        if not _allowed(f.filename):
            rejected.append(f.filename)
            continue
        dest = job_dir / Path(f.filename).name
        f.save(dest)
        saved.append(dest)

    if not saved:
        shutil.rmtree(job_dir, ignore_errors=True)
        return jsonify({"error": "No supported files uploaded", "rejected": rejected}), 400

    with _jobs_lock:
        _jobs[job_id] = {
            "status":     "processing",
            "created_at": datetime.utcnow().isoformat() + "Z",
            "files":      [p.name for p in saved],
            "results":    [],
            "errors":     [],
        }

    thread = threading.Thread(target=_run_conversion, args=(job_id, saved), daemon=True)
    thread.start()

    return jsonify({
        "job_id":   job_id,
        "status":   "processing",
        "files":    [p.name for p in saved],
        "rejected": rejected,
    })


@app.route("/status/<job_id>")
def status(job_id: str):
    with _jobs_lock:
        job = _jobs.get(job_id)
    if not job:
        return jsonify({"error": "Job not found"}), 404
    return jsonify({**job, "job_id": job_id})


@app.route("/download/<job_id>")
def download(job_id: str):
    with _jobs_lock:
        job = _jobs.get(job_id)

    if not job:
        return jsonify({"error": "Job not found"}), 404
    if job["status"] == "processing":
        return jsonify({"error": "Job still processing"}), 202

    out_dir = _job_output_dir(job_id)
    if not out_dir.exists():
        return jsonify({"error": "Output not found"}), 404

    # Stream a zip of the output directory
    zip_path = OUTPUT_DIR / f"{job_id}.zip"
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for path in out_dir.rglob("*"):
            if path.is_file():
                zf.write(path, path.relative_to(out_dir))

    return send_file(
        zip_path,
        as_attachment=True,
        download_name="converted_documents.zip",
        mimetype="application/zip",
    )


@app.route("/jobs")
def list_jobs():
    with _jobs_lock:
        snapshot = {jid: {**data, "job_id": jid} for jid, data in _jobs.items()}
    return jsonify(list(snapshot.values()))


# ── ContractTwin routes ─────────────────────────────────────────────────────

# Cache the demo contract result so we don't re-parse on every request
_demo_cache = {}


def _build_full_response(clauses, graph):
    """Assemble the full ContractTwin JSON response with economics."""
    # Compute economics for each clause
    all_econ = {}
    all_mc = {}
    for clause in clauses:
        econ = compute_clause_economics(clause)
        all_econ[clause["id"]] = econ
        mc = monte_carlo_simulation(econ, n=500, seed=hash(clause["id"]) % 2**31)
        all_mc[clause["id"]] = mc

    # Compute interaction effects and recommendations
    for clause in clauses:
        cid = clause["id"]
        interaction = compute_interaction_effects(clause, graph, all_econ)
        all_econ[cid].update(interaction)

        recs = generate_recommendations(clause, all_econ[cid], interaction)
        clause["economics"] = {
            **all_econ[cid],
            "monte_carlo": all_mc[cid],
        }
        clause["recommendations"] = recs

        # Add plain English translation
        translation = translate_clause(clause)
        clause["plain_english"] = translation["plain_english"]
        clause["what_matters"] = translation["what_matters"]
        clause["watch_for"] = translation["watch_for"]
        clause["role_views"] = translation["role_views"]

        # Time profile
        clause["time_profile"] = compute_time_profile(all_econ[cid])

    # Portfolio summary
    portfolio = compute_portfolio_summary(all_econ, all_mc)

    # Collect all recommendations across clauses, sort by priority
    all_recs = []
    for clause in clauses:
        for rec in clause.get("recommendations", []):
            all_recs.append({**rec, "clause_id": clause["id"], "clause_title": clause["title"]})
    all_recs.sort(key=lambda r: r["priority_score"], reverse=True)
    portfolio["highest_roi_fixes"] = all_recs[:10]

    # Scenario summaries
    scenarios = get_all_scenario_summaries(clauses, graph)

    return {
        "clauses": clauses,
        "graph": graph,
        "zones": ZONES,
        "portfolio_summary": portfolio,
        "scenarios": scenarios,
    }


@app.route("/contracttwin")
def contracttwin():
    return render_template("contracttwin.html")


@app.route("/contracttwin/demo")
def contracttwin_demo():
    if not _demo_cache:
        text = get_demo_contract()
        parsed = parse_contract(text)
        graph = build_graph(parsed["clauses"])
        response = _build_full_response(parsed["clauses"], graph)
        response["contract_id"] = parsed["contract_id"]
        response["title"] = parsed["title"]
        _demo_cache["data"] = response
    return jsonify(_demo_cache["data"])


@app.route("/contracttwin/parse", methods=["POST"])
def contracttwin_parse():
    data = request.get_json(silent=True) or {}
    text = data.get("text", "")
    if not text and request.form:
        text = request.form.get("text", "")
    if not text:
        return jsonify({"error": "No contract text provided"}), 400
    if len(text) < 100:
        return jsonify({"error": "Contract text too short"}), 400

    parsed = parse_contract(text)
    graph = build_graph(parsed["clauses"])
    response = _build_full_response(parsed["clauses"], graph)
    response["contract_id"] = parsed["contract_id"]
    response["title"] = parsed["title"]
    return jsonify(response)


@app.route("/contracttwin/scenarios/<scenario_id>")
def contracttwin_scenario(scenario_id):
    if scenario_id not in SCENARIOS:
        return jsonify({"error": f"Unknown scenario: {scenario_id}"}), 404

    # Use demo contract for scenario runs (or could accept contract_id)
    text = get_demo_contract()
    parsed = parse_contract(text)
    graph = build_graph(parsed["clauses"])
    result = run_scenario(scenario_id, parsed["clauses"], graph)
    return jsonify(result)


# ── startup ──────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    UPLOAD_DIR.mkdir(exist_ok=True)
    OUTPUT_DIR.mkdir(exist_ok=True)
    app.run(host="0.0.0.0", port=5000, debug=False)
