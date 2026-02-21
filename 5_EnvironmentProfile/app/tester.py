"""
Test-profile one-shot runner — exercises every API endpoint and exits 0/1.
Behaviour adapts to the env reported by /health (dev vs non-dev /debug rule).
"""
import os
import sys
import json
import urllib.request
import urllib.error

API_URL = os.environ.get("API_URL", "http://api:5000")

PASS = 0
FAIL = 0


def get(path):
    with urllib.request.urlopen(f"{API_URL}{path}", timeout=10) as r:
        return json.loads(r.read()), r.status


def post(path, data):
    body = json.dumps(data).encode()
    req  = urllib.request.Request(
        f"{API_URL}{path}", data=body,
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=10) as r:
        return json.loads(r.read()), r.status


def check(name, condition, detail=""):
    global PASS, FAIL
    if condition:
        print(f"  PASS  {name}", flush=True)
        PASS = PASS + 1
    else:
        print(f"  FAIL  {name}{': ' + detail if detail else ''}", flush=True)
        FAIL = FAIL + 1


print("[TESTER] running API integration tests …", flush=True)

# ── 1: health ──────────────────────────────────────────────────────────────
data, status = get("/health")
check("GET /health returns 200",   status == 200)
check("health.status == ok",       data.get("status") == "ok")

# learn which env the api is running in
api_env = data.get("env", "unknown")
print(f"[TESTER] api reports APP_ENV={api_env}", flush=True)

# ── 2: store a value ───────────────────────────────────────────────────────
data, status = post("/data", {"key": "tester-key", "value": "hello-42"})
check("POST /data returns 200",    status == 200)
check("POST /data ok=True",        data.get("ok") is True)

# ── 3: retrieve the value ──────────────────────────────────────────────────
data, status = get("/data/tester-key")
check("GET /data/<key> returns 200",     status == 200)
check("GET /data/<key> correct value",   data.get("value") == "hello-42")

# ── 4: 404 for unknown key ─────────────────────────────────────────────────
try:
    get("/data/no-such-key-xyz")
    check("GET /data/missing returns 404", False, "expected HTTPError")
except urllib.error.HTTPError as e:
    check("GET /data/missing returns 404", e.code == 404)

# ── 5: stats ───────────────────────────────────────────────────────────────
data, status = get("/stats")
check("GET /stats returns 200",          status == 200)
check("stats has uptime_seconds",        "uptime_seconds" in data)
check("stats has requests map",          isinstance(data.get("requests"), dict))

# ── 6: /debug access control ──────────────────────────────────────────────
if api_env == "development":
    data, status = get("/debug")
    check("GET /debug available in dev",  status == 200)
    check("debug shows store dict",       isinstance(data.get("store"), dict))
else:
    try:
        get("/debug")
        check("GET /debug blocked in non-dev", False, "expected 403")
    except urllib.error.HTTPError as e:
        check("GET /debug blocked in non-dev", e.code == 403)

# ── summary ────────────────────────────────────────────────────────────────
total = PASS + FAIL
print(f"\n[TESTER] {PASS}/{total} passed", flush=True)
sys.exit(0 if FAIL == 0 else 1)
