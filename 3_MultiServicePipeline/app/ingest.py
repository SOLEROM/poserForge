"""
Ingest — stage 1 of the pipeline.
Assigns a UUID job_id to each submission and forwards to normalize.
"""
import os
import uuid
import requests
from flask import Flask, request, jsonify

app = Flask(__name__)

NORMALIZE_URL = os.environ.get("NORMALIZE_URL", "http://normalize:5002")


@app.route("/health")
def health():
    return jsonify({"status": "ok", "service": "ingest"})


@app.route("/ingest", methods=["POST"])
def ingest():
    body = request.get_json(force=True) or {}
    text = body.get("text", "")
    job_id = str(uuid.uuid4())

    try:
        resp = requests.post(f"{NORMALIZE_URL}/normalize",
                             json={"job_id": job_id, "text": text}, timeout=10)
        resp.raise_for_status()
    except requests.RequestException as exc:
        return jsonify({"error": f"normalize unavailable: {exc}"}), 502

    return jsonify({"job_id": job_id, "status": "accepted"})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5001)
