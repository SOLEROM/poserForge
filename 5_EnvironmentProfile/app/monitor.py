"""
Prod-profile monitor — periodic health polling with structured output and alerting.
Only activated when Compose is started with --profile prod.
"""
import os
import time
import json
import urllib.request
import urllib.error

API_URL       = os.environ.get("API_URL", "http://api:5000")
POLL_INTERVAL = int(os.environ.get("POLL_INTERVAL", 5))


def get(path):
    try:
        with urllib.request.urlopen(f"{API_URL}{path}", timeout=5) as r:
            return json.loads(r.read()), r.status
    except urllib.error.HTTPError as e:
        return {"error": str(e)}, e.code
    except Exception as e:
        return {"error": str(e)}, 0


def log_ok(msg):
    print(json.dumps({"level": "info",  "source": "monitor", "msg": msg}), flush=True)


def log_alert(msg):
    print(json.dumps({"level": "ALERT", "source": "monitor", "msg": msg}), flush=True)


print(json.dumps({"level": "info", "source": "monitor",
                  "msg": f"started — polling {API_URL} every {POLL_INTERVAL}s"}), flush=True)

consecutive_failures = 0

while True:
    health_data, health_status = get("/health")
    stats_data,  stats_status  = get("/stats")

    if health_status == 200 and health_data.get("status") == "ok":
        consecutive_failures = 0
        uptime     = stats_data.get("uptime_seconds", "?")
        reqs       = stats_data.get("requests", {})
        total_reqs = sum(reqs.values()) if isinstance(reqs, dict) else "?"
        log_ok(f"healthy | env={health_data.get('env')} "
               f"uptime={uptime}s total_requests={total_reqs}")
    else:
        consecutive_failures = consecutive_failures + 1
        log_alert(f"health check failed (http={health_status} "
                  f"consecutive={consecutive_failures})")
        if consecutive_failures >= 3:
            log_alert("service appears DOWN — 3 consecutive failures")

    time.sleep(POLL_INTERVAL)
