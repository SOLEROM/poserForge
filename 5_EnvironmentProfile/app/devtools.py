"""
Dev-profile companion — polls /health, /debug, /stats and prints a live dashboard.
Only activated when Compose is started with --profile dev.
"""
import os
import time
import json
import urllib.request

API_URL       = os.environ.get("API_URL", "http://api:5000")
POLL_INTERVAL = int(os.environ.get("POLL_INTERVAL", 3))


def get(path):
    try:
        with urllib.request.urlopen(f"{API_URL}{path}", timeout=5) as r:
            return json.loads(r.read())
    except Exception as e:
        return {"error": str(e)}


print(f"[DEVTOOLS] started — polling {API_URL} every {POLL_INTERVAL}s", flush=True)

poll = 0
while True:
    poll += 1
    health = get("/health")
    debug  = get("/debug")
    stats  = get("/stats")

    print(f"\n[DEVTOOLS] ── poll #{poll} ──────────────────────────────", flush=True)
    print(f"  status  : {health.get('status', '?')}  env={health.get('env', '?')}", flush=True)
    print(f"  uptime  : {stats.get('uptime_seconds', '?')}s", flush=True)
    print(f"  requests: {stats.get('requests', {})}", flush=True)
    store = debug.get("store", {})
    print(f"  store   : {store} ({len(store)} keys)", flush=True)
    if "error" in debug:
        print(f"  debug   : {debug['error']}", flush=True)

    time.sleep(POLL_INTERVAL)
