"""
Analyze — stage 3 (final stage) of the pipeline.
Computes word-frequency statistics and persists results
as JSON to the shared data volume.
"""
import os
import json
from collections import Counter
from flask import Flask, request, jsonify

app = Flask(__name__)

DATA_DIR = os.environ.get("DATA_DIR", "/data")


@app.route("/health")
def health():
    return jsonify({"status": "ok", "service": "analyze"})


@app.route("/analyze", methods=["POST"])
def analyze():
    body  = request.get_json(force=True) or {}
    job_id = body.get("job_id", "")
    words  = body.get("words", [])

    freq = Counter(words)
    result = {
        "job_id":        job_id,
        "total_words":   len(words),
        "unique_words":  len(freq),
        "top_words":     freq.most_common(5),
        "avg_word_len":  round(sum(len(w) for w in words) / len(words), 2) if words else 0,
    }

    os.makedirs(DATA_DIR, exist_ok=True)
    out_path = os.path.join(DATA_DIR, f"{job_id}.json")
    with open(out_path, "w") as fh:
        json.dump(result, fh, indent=2)

    return jsonify({"job_id": job_id, "status": "stored"})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5003)
