"""
Normalize — stage 2 of the pipeline.
Lowercases text, strips punctuation, splits into word tokens,
then forwards the token list to the analyze service.
"""
import os
import re
import requests
from flask import Flask, request, jsonify

app = Flask(__name__)

ANALYZE_URL = os.environ.get("ANALYZE_URL", "http://analyze:5003")


@app.route("/health")
def health():
    return jsonify({"status": "ok", "service": "normalize"})


@app.route("/normalize", methods=["POST"])
def normalize():
    body = request.get_json(force=True) or {}
    job_id = body.get("job_id", "")
    text   = body.get("text", "")

    clean = re.sub(r"[^a-z0-9\s]", "", text.lower())
    words = [w for w in clean.split() if w]

    try:
        resp = requests.post(f"{ANALYZE_URL}/analyze",
                             json={"job_id": job_id, "words": words}, timeout=10)
        resp.raise_for_status()
    except requests.RequestException as exc:
        return jsonify({"error": f"analyze unavailable: {exc}"}), 502

    return jsonify({"job_id": job_id, "word_count": len(words)})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5002)
