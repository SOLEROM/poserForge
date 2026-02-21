#!/usr/bin/env python3
"""
Primary application service — the workload being observed.

Exposes:
  GET  /health   — liveness probe
  POST /process  — simulate work; logs task in/out; returns result
  POST /fail     — simulate failure; logs error; returns 500
  GET  /metrics  — Prometheus-style text metrics

Writes structured JSONL to /logs/app.log so sidecars can observe without
any code changes to this service.
"""

import json
import os
import time
import threading
from datetime import datetime, timezone
from http.server import HTTPServer, BaseHTTPRequestHandler
from socketserver import ThreadingMixIn
from urllib.parse import urlparse

LOG_PATH = "/logs/app.log"
PORT = int(os.environ.get("PORT", 8080))

_lock = threading.Lock()
_counters = {
    "requests_total": 0,
    "requests_ok": 0,
    "requests_err": 0,
    "process_total": 0,
    "process_ok": 0,
    "process_err": 0,
    "start_time": time.time(),
}


def log(level, msg, **extra):
    entry = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "level": level,
        "msg": msg,
        **extra,
    }
    os.makedirs("/logs", exist_ok=True)
    with open(LOG_PATH, "a") as f:
        f.write(json.dumps(entry) + "\n")
    print(json.dumps(entry), flush=True)


class Handler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        pass  # suppress default HTTP server noise

    def do_GET(self):
        with _lock:
            _counters["requests_total"] += 1

        path = urlparse(self.path).path

        if path == "/health":
            with _lock:
                uptime = round(time.time() - _counters["start_time"], 1)
                _counters["requests_ok"] += 1
            log("INFO", "health check", uptime_s=uptime)
            self._json(200, {"status": "ok", "uptime_s": uptime})

        elif path == "/metrics":
            self._metrics()

        else:
            with _lock:
                _counters["requests_err"] += 1
            self._json(404, {"error": "not found", "path": path})

    def do_POST(self):
        with _lock:
            _counters["requests_total"] += 1

        path = urlparse(self.path).path
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length).decode() if length else "{}"
        try:
            data = json.loads(body)
        except json.JSONDecodeError:
            data = {}

        if path == "/process":
            self._handle_process(data)
        elif path == "/fail":
            self._handle_fail(data)
        else:
            with _lock:
                _counters["requests_err"] += 1
            self._json(404, {"error": "not found", "path": path})

    def _handle_process(self, data):
        with _lock:
            _counters["process_total"] += 1

        task = data.get("task", "unnamed-task")
        log("INFO", "processing task", task=task)

        t0 = time.time()
        time.sleep(0.05)  # simulate work
        result = f"done:{task}:{int(time.time())}"
        elapsed = round(time.time() - t0, 3)

        with _lock:
            _counters["process_ok"] += 1
            _counters["requests_ok"] += 1

        log("INFO", "task complete", task=task, elapsed_s=elapsed, result=result)
        self._json(200, {"result": result, "elapsed_s": elapsed})

    def _handle_fail(self, data):
        reason = data.get("reason", "simulated-failure")
        with _lock:
            _counters["process_err"] += 1
            _counters["requests_err"] += 1
        log("ERROR", "task failed", reason=reason)
        self._json(500, {"error": reason})

    def _metrics(self):
        with _lock:
            c = dict(_counters)
        uptime = round(time.time() - c["start_time"], 1)

        lines = [
            "# HELP requests_total Total HTTP requests received",
            "# TYPE requests_total counter",
            f"requests_total {c['requests_total']}",
            "# HELP requests_ok Successful HTTP responses",
            "# TYPE requests_ok counter",
            f"requests_ok {c['requests_ok']}",
            "# HELP requests_err Error HTTP responses",
            "# TYPE requests_err counter",
            f"requests_err {c['requests_err']}",
            "# HELP process_total Total /process calls",
            "# TYPE process_total counter",
            f"process_total {c['process_total']}",
            "# HELP process_ok Successful /process calls",
            "# TYPE process_ok counter",
            f"process_ok {c['process_ok']}",
            "# HELP process_err Failed /process calls",
            "# TYPE process_err counter",
            f"process_err {c['process_err']}",
            "# HELP uptime_seconds Application uptime in seconds",
            "# TYPE uptime_seconds gauge",
            f"uptime_seconds {uptime}",
            "",
        ]
        body = "\n".join(lines).encode()
        self.send_response(200)
        self.send_header("Content-Type", "text/plain; version=0.0.4")
        self.send_header("Content-Length", len(body))
        self.end_headers()
        self.wfile.write(body)
        log("INFO", "metrics scraped")

    def _json(self, code, data):
        body = json.dumps(data).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", len(body))
        self.end_headers()
        self.wfile.write(body)


class ThreadedHTTPServer(ThreadingMixIn, HTTPServer):
    """Handle each request in a separate thread."""
    daemon_threads = True


if __name__ == "__main__":
    os.makedirs("/logs", exist_ok=True)
    log("INFO", "app starting", port=PORT)
    server = ThreadedHTTPServer(("0.0.0.0", PORT), Handler)
    log("INFO", "app ready", port=PORT)
    server.serve_forever()
