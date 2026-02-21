"""
Gateway — public-facing HTTP API.
Routes POST /submit to the ingest service.
Serves GET /result/<job_id> from the shared data volume.
"""
import os
import json
import requests
from flask import Flask, request, jsonify

app = Flask(__name__)

INGEST_URL = os.environ.get("INGEST_URL", "http://ingest:5001")
DATA_DIR   = os.environ.get("DATA_DIR", "/data")


@app.route("/health")
def health():
    return jsonify({"status": "ok", "service": "gateway"})


@app.route("/submit", methods=["POST"])
def submit():
    body = request.get_json(force=True) or {}
    text = body.get("text", "").strip()
    if not text:
        return jsonify({"error": "text is required"}), 400

    try:
        resp = requests.post(f"{INGEST_URL}/ingest",
                             json={"text": text}, timeout=10)
        resp.raise_for_status()
    except requests.RequestException as exc:
        return jsonify({"error": f"ingest unavailable: {exc}"}), 502

    return jsonify(resp.json()), 202


@app.route("/result/<job_id>")
def result(job_id):
    path = os.path.join(DATA_DIR, f"{job_id}.json")
    if not os.path.isfile(path):
        return jsonify({"error": "not found", "job_id": job_id}), 404
    with open(path) as fh:
        return jsonify(json.load(fh))


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8088)
