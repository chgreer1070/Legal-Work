"""
Outlook-to-PDF Converter – Flask web application.

Routes
------
GET  /              Drag-and-drop upload page
POST /convert       Accept uploaded files, run conversion, return JSON status
GET  /download/<id> Download a converted output bundle (zip)
GET  /jobs          List recent conversion jobs (JSON)
"""

import json
import logging
import os
import shutil
import tempfile
import threading
import time
import uuid
import zipfile
from datetime import datetime, timezone
from pathlib import Path

from flask import (
    Flask,
    after_this_request,
    jsonify,
    render_template,
    request,
    send_file,
    url_for,
)

logger = logging.getLogger(__name__)

from converter import convert_standalone, msg_to_pdf

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 200 * 1024 * 1024  # 200 MB

UPLOAD_DIR  = Path("uploads")
OUTPUT_DIR  = Path("output")
ALLOWED_EXT = {".msg", ".pdf", ".doc", ".docx", ".ppt", ".pptx"}

# In-memory job store: { job_id: { status, message, files, created_at } }
_jobs: dict[str, dict] = {}
_jobs_lock = threading.Lock()
_MAX_JOBS = 1000
_JOB_TTL_SECONDS = 3600  # 1 hour


def _cleanup_expired_jobs():
    """Remove jobs older than _JOB_TTL_SECONDS and enforce max store size."""
    now = time.time()
    with _jobs_lock:
        expired = [
            jid for jid, data in _jobs.items()
            if now - data.get("_created_ts", 0) > _JOB_TTL_SECONDS
        ]
        for jid in expired:
            _jobs.pop(jid, None)
        # Enforce max size by removing oldest jobs
        if len(_jobs) > _MAX_JOBS:
            sorted_jobs = sorted(_jobs.items(), key=lambda x: x[1].get("_created_ts", 0))
            for jid, _ in sorted_jobs[: len(_jobs) - _MAX_JOBS]:
                _jobs.pop(jid, None)


def _start_cleanup_thread():
    """Background thread that periodically removes expired jobs."""
    def _run():
        while True:
            time.sleep(300)  # Run every 5 minutes
            _cleanup_expired_jobs()
    t = threading.Thread(target=_run, daemon=True)
    t.start()


_start_cleanup_thread()


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
        _cleanup_expired_jobs()
        _jobs[job_id] = {
            "status":     "processing",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "_created_ts": time.time(),
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

    @after_this_request
    def _cleanup(response):
        try:
            zip_path.unlink(missing_ok=True)
        except OSError:
            pass
        return response

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


# ── startup ──────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    UPLOAD_DIR.mkdir(exist_ok=True)
    OUTPUT_DIR.mkdir(exist_ok=True)
    app.run(host="0.0.0.0", port=5000, debug=False)
