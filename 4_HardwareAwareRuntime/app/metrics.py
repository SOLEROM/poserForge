#!/usr/bin/env python3
"""
HTTP metrics dashboard — exposes sensor readings stored on the shared volume.

Endpoints:
  GET /health           → {"status": "ok"}
  GET /latest           → most recent sensor reading
  GET /history?n=<N>    → last N readings (default 20)
  GET /stats            → min/max/avg over last 100 readings
"""

import json
import os
from http.server import BaseHTTPRequestHandler, HTTPServer

LATEST_PATH = "/data/latest.json"
HISTORY_PATH = "/data/history.jsonl"
PORT = 8080  # fixed internal container port; host binding is set by METRICS_PORT in compose


class MetricsHandler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):  # silence default access log
        pass

    def send_json(self, code: int, data: dict):
        body = json.dumps(data, indent=2).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        path = self.path.split("?")[0]

        if path == "/health":
            self.send_json(200, {"status": "ok", "service": "metrics"})

        elif path == "/latest":
            try:
                with open(LATEST_PATH) as f:
                    data = json.load(f)
                self.send_json(200, data)
            except (FileNotFoundError, json.JSONDecodeError):
                self.send_json(503, {"error": "no data yet"})

        elif path == "/history":
            n = 20
            if "?" in self.path:
                for part in self.path.split("?", 1)[1].split("&"):
                    if part.startswith("n="):
                        try:
                            n = int(part[2:])
                        except ValueError:
                            pass
            try:
                with open(HISTORY_PATH) as f:
                    lines = f.readlines()
                readings = [json.loads(l) for l in lines[-n:] if l.strip()]
                self.send_json(200, {"count": len(readings), "readings": readings})
            except FileNotFoundError:
                self.send_json(200, {"count": 0, "readings": []})

        elif path == "/stats":
            try:
                with open(HISTORY_PATH) as f:
                    lines = f.readlines()
                readings = [json.loads(l) for l in lines[-100:] if l.strip()]
                if not readings:
                    self.send_json(200, {"error": "no data"})
                    return

                def agg(vals):
                    return {
                        "min": round(min(vals), 2),
                        "max": round(max(vals), 2),
                        "avg": round(sum(vals) / len(vals), 2),
                    }

                self.send_json(200, {
                    "samples": len(readings),
                    "source": readings[-1].get("source", "unknown"),
                    "temp_c": agg([r["temp_c"] for r in readings]),
                    "pressure_hpa": agg([r["pressure_hpa"] for r in readings]),
                    "humidity_pct": agg([r["humidity_pct"] for r in readings]),
                })
            except FileNotFoundError:
                self.send_json(200, {"error": "no data"})

        else:
            self.send_json(404, {"error": "not found"})


def main():
    print(f"[metrics] Listening on http://0.0.0.0:{PORT}", flush=True)
    server = HTTPServer(("0.0.0.0", PORT), MetricsHandler)
    server.serve_forever()


if __name__ == "__main__":
    main()
