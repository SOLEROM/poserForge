"""
Environment-aware API — behaviour driven by APP_ENV.

  development : verbose debug logging, /debug endpoint exposed
  test        : minimal output, /debug blocked (403)
  production  : structured JSON logging, /debug blocked (403)
"""
import os
import time
import json
from flask import Flask, request, jsonify

app = Flask(__name__)

APP_ENV   = os.environ.get("APP_ENV", "development")
DATA_FILE = "/data/store.json"

start_time     = time.time()
request_counts = {}


def log(msg):
    if APP_ENV == "development":
        print(f"[DEV] {msg}", flush=True)
    elif APP_ENV == "production":
        print(json.dumps({"level": "info", "env": APP_ENV, "msg": msg}), flush=True)
    # test: silent


def load_store():
    try:
        with open(DATA_FILE) as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def save_store(data):
    os.makedirs(os.path.dirname(DATA_FILE), exist_ok=True)
    tmp = DATA_FILE + ".tmp"
    with open(tmp, "w") as f:
        json.dump(data, f)
    os.rename(tmp, DATA_FILE)


@app.before_request
def count_request():
    request_counts[request.path] = request_counts.get(request.path, 0) + 1


@app.route("/health")
def health():
    log("health check")
    return jsonify({"status": "ok", "env": APP_ENV})


@app.route("/data", methods=["POST"])
def set_data():
    body  = request.get_json()
    key   = body.get("key")
    value = body.get("value")
    store = load_store()
    store[key] = value
    save_store(store)
    log(f"set {key}={value}")
    return jsonify({"ok": True, "key": key})


@app.route("/data/<key>")
def get_data(key):
    store = load_store()
    if key not in store:
        return jsonify({"error": "not found"}), 404
    log(f"get {key}={store[key]}")
    return jsonify({"key": key, "value": store[key]})


@app.route("/stats")
def stats():
    return jsonify({
        "env":            APP_ENV,
        "uptime_seconds": round(time.time() - start_time, 1),
        "requests":       request_counts,
    })


@app.route("/debug")
def debug():
    if APP_ENV != "development":
        return jsonify({"error": "debug endpoint only available in development mode"}), 403
    store = load_store()
    return jsonify({
        "env":            APP_ENV,
        "store":          store,
        "request_counts": request_counts,
        "uptime_seconds": round(time.time() - start_time, 1),
        "pid":            os.getpid(),
    })


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    print(f"[API] starting — APP_ENV={APP_ENV} port={port}", flush=True)
    app.run(host="0.0.0.0", port=port, debug=False, use_reloader=False)
