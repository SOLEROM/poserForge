#!/usr/bin/env python3
"""
Job Tracker Service — long-running daemon.

Owns the job registry, persists state to the shared workspace volume,
and exposes an HTTP API consumed by the tool containers.
"""

import json
import os
import threading
import time
import uuid
from datetime import datetime
from pathlib import Path

from flask import Flask, jsonify, request

app = Flask(__name__)

WORKSPACE = Path(os.environ.get("WORKSPACE", "/workspace"))
JOBS_FILE = WORKSPACE / "jobs.json"
_lock = threading.Lock()


def load_jobs() -> dict:
    WORKSPACE.mkdir(parents=True, exist_ok=True)
    if JOBS_FILE.exists():
        return json.loads(JOBS_FILE.read_text())
    return {}


def save_jobs(jobs: dict) -> None:
    WORKSPACE.mkdir(parents=True, exist_ok=True)
    JOBS_FILE.write_text(json.dumps(jobs, indent=2))


def _process_job(job_id: str) -> None:
    """Simulate async job processing (completes after 1 s)."""
    time.sleep(1)
    with _lock:
        jobs = load_jobs()
        if job_id in jobs:
            jobs[job_id]["status"] = "completed"
            jobs[job_id]["completed_at"] = datetime.utcnow().isoformat() + "Z"
            save_jobs(jobs)


# ── Routes ─────────────────────────────────────────────────────────────────────

@app.route("/health")
def health():
    return jsonify({"status": "ok", "service": "job-tracker"})


@app.route("/jobs", methods=["GET"])
def list_jobs():
    with _lock:
        jobs = load_jobs()
    return jsonify({"jobs": list(jobs.values()), "count": len(jobs)})


@app.route("/jobs", methods=["POST"])
def submit_job():
    data = request.get_json(force=True) or {}
    job = {
        "id": str(uuid.uuid4())[:8],
        "name": data.get("name", "unnamed"),
        "cmd": data.get("cmd", ""),
        "status": "pending",
        "submitted_at": datetime.utcnow().isoformat() + "Z",
        "completed_at": None,
    }
    with _lock:
        jobs = load_jobs()
        jobs[job["id"]] = job
        save_jobs(jobs)

    threading.Thread(target=_process_job, args=(job["id"],), daemon=True).start()
    return jsonify(job), 201


@app.route("/jobs/<job_id>", methods=["GET"])
def get_job(job_id: str):
    with _lock:
        jobs = load_jobs()
    job = jobs.get(job_id)
    if not job:
        return jsonify({"error": f"Job {job_id!r} not found"}), 404
    return jsonify(job)


if __name__ == "__main__":
    print("Job Tracker Service starting on :8080", flush=True)
    app.run(host="0.0.0.0", port=8080, debug=False)
