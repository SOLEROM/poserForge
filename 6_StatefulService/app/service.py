#!/usr/bin/env python3
"""
Stateful session service.

Demonstrates persistent application state: all durable data lives in /data
(a named volume), so the container itself is disposable — restart, rebuild,
or crash without losing sessions, the event log, or lifecycle counters.
"""

import json
import os
import sys
import time
import uuid
from pathlib import Path

from flask import Flask, abort, jsonify, request

PORT      = int(os.environ.get("PORT", 8080))
DATA_DIR  = Path(os.environ.get("DATA_DIR", "/data"))

SESSIONS_DIR = DATA_DIR / "sessions"
EVENTS_FILE  = DATA_DIR / "events.jsonl"
STATS_FILE   = DATA_DIR / "stats.json"

# ── In-memory identity (new value every container start) ──────────────────────
CONTAINER_ID  = str(uuid.uuid4())[:8]
START_TIME    = time.time()
req_count     = 0   # requests served this container instance

# ── Volume helpers ─────────────────────────────────────────────────────────────

def _load_stats() -> dict:
    if STATS_FILE.exists():
        return json.loads(STATS_FILE.read_text())
    return {"startup_count": 0, "crash_count": 0,
            "total_sessions": 0, "total_requests": 0}


def _save_stats(s: dict) -> None:
    tmp = STATS_FILE.with_suffix(".tmp")
    tmp.write_text(json.dumps(s, indent=2))
    tmp.rename(STATS_FILE)


def _log_event(kind: str, **extra) -> None:
    entry = {
        "ts":        time.time(),
        "time":      time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "event":     kind,
        "container": CONTAINER_ID,
        **extra,
    }
    with open(EVENTS_FILE, "a") as f:
        f.write(json.dumps(entry) + "\n")


def _session_path(sid: str) -> Path:
    return SESSIONS_DIR / f"{sid}.json"


def _load_session(sid: str) -> dict:
    p = _session_path(sid)
    if not p.exists():
        abort(404, description=f"Session {sid} not found")
    return json.loads(p.read_text())


def _save_session(sess: dict) -> None:
    p   = _session_path(sess["id"])
    tmp = p.with_suffix(".tmp")
    tmp.write_text(json.dumps(sess, indent=2))
    tmp.rename(p)


# ── Bootstrap ─────────────────────────────────────────────────────────────────
DATA_DIR.mkdir(parents=True, exist_ok=True)
SESSIONS_DIR.mkdir(exist_ok=True)

_stats = _load_stats()
_stats["startup_count"] = _stats.get("startup_count", 0) + 1
_save_stats(_stats)
_log_event("startup",
           startup_count=_stats["startup_count"],
           crash_count=_stats["crash_count"])

# ── Flask app ─────────────────────────────────────────────────────────────────
app = Flask(__name__)


@app.before_request
def _count():
    global req_count
    req_count += 1


# ── Routes ────────────────────────────────────────────────────────────────────

@app.get("/health")
def health():
    return jsonify(status="ok",
                   container=CONTAINER_ID,
                   uptime=round(time.time() - START_TIME, 1))


@app.get("/state")
def state():
    s        = _load_stats()
    sessions = list(SESSIONS_DIR.glob("*.json"))
    return jsonify(
        container_id=CONTAINER_ID,
        uptime_seconds=round(time.time() - START_TIME, 1),
        requests_this_instance=req_count,
        # persisted — survive every restart / rebuild / crash
        startup_count=s["startup_count"],
        crash_count=s["crash_count"],
        total_sessions=s["total_sessions"],
        total_requests=s["total_requests"],
        live_sessions=len(sessions),
    )


@app.post("/sessions")
def create_session():
    body = request.get_json(silent=True) or {}
    sid  = str(uuid.uuid4())
    now  = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    sess = {
        "id":           sid,
        "name":         body.get("name", "unnamed"),
        "data":         body.get("data", {}),
        "created_at":   now,
        "last_active":  now,
        "access_count": 0,
    }
    _save_session(sess)
    _log_event("session_created", session_id=sid, name=sess["name"])
    s = _load_stats()
    s["total_sessions"] = s.get("total_sessions", 0) + 1
    _save_stats(s)
    return jsonify(sess), 201


@app.get("/sessions")
def list_sessions():
    sessions = [json.loads(p.read_text())
                for p in sorted(SESSIONS_DIR.glob("*.json"))]
    return jsonify(sessions=sessions, count=len(sessions))


@app.get("/sessions/<sid>")
def get_session(sid):
    return jsonify(_load_session(sid))


@app.put("/sessions/<sid>")
def update_session(sid):
    sess = _load_session(sid)
    body = request.get_json(silent=True) or {}
    if "name" in body:
        sess["name"] = body["name"]
    if "data" in body:
        sess["data"] = body["data"]
    sess["last_active"]  = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    sess["access_count"] = sess.get("access_count", 0) + 1
    _save_session(sess)
    _log_event("session_updated", session_id=sid)
    return jsonify(sess)


@app.delete("/sessions/<sid>")
def delete_session(sid):
    _load_session(sid)   # raises 404 if missing
    _session_path(sid).unlink()
    _log_event("session_deleted", session_id=sid)
    return jsonify(status="deleted", id=sid)


@app.get("/events")
def list_events():
    if not EVENTS_FILE.exists():
        return jsonify(events=[], count=0)
    events = [json.loads(line)
              for line in EVENTS_FILE.read_text().splitlines()
              if line.strip()]
    limit  = int(request.args.get("limit", 50))
    return jsonify(events=events[-limit:], count=len(events))


@app.post("/crash")
def crash():
    """Simulate a crash — increments crash_count then force-exits."""
    s = _load_stats()
    s["crash_count"] = s.get("crash_count", 0) + 1
    _save_stats(s)
    _log_event("crash_triggered", crash_count=s["crash_count"])
    sys.stdout.flush()
    os._exit(1)   # bypass Python cleanup to simulate hard crash


# ── Entry ─────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print(f"[service] container={CONTAINER_ID} port={PORT}", flush=True)
    app.run(host="0.0.0.0", port=PORT)
