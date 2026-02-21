#!/usr/bin/env bash
# Integration tests for 8_ObservabilitySidecar
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR/.."

set -a; source .env; set +a

PASS=0; FAIL=0
COMPOSE="docker compose"
PORT="${APP_PORT:-8092}"
VOLUME="poserforge-sidecar-logs"

pass() { echo "  PASS: $1"; PASS=$((PASS+1)); }
fail() { echo "  FAIL: $1"; FAIL=$((FAIL+1)); }

check() {
  local desc="$1"; shift
  if eval "$@" >/dev/null 2>&1; then pass "$desc"; else fail "$desc"; fi
}

# ── Setup ─────────────────────────────────────────────────────────────────────
echo ""
echo "=== Setup ==="
$COMPOSE --profile observe --profile debug down -v 2>/dev/null || true
docker volume rm "$VOLUME" 2>/dev/null || true

# ── Build ─────────────────────────────────────────────────────────────────────
echo ""
echo "=== Build ==="
check "image builds cleanly" \
  "$COMPOSE build"

# ── App service ───────────────────────────────────────────────────────────────
echo ""
echo "=== App Service ==="
$COMPOSE up -d
echo "  waiting for app to become healthy..."
sleep 6

check "app container is running" \
  "docker ps --format '{{.Names}}' | grep -q '8_observabilitysidecar-app\|8observabilitysidecar.app\|app'"

check "GET /health returns HTTP 200" \
  "curl -sf http://localhost:$PORT/health"

HEALTH=$(curl -s "http://localhost:$PORT/health")
check "/health body has status=ok" \
  "echo '$HEALTH' | python3 -c \"import sys,json; d=json.load(sys.stdin); assert d['status']=='ok'\""

check "/health body has uptime_s field" \
  "echo '$HEALTH' | python3 -c \"import sys,json; d=json.load(sys.stdin); assert 'uptime_s' in d\""

# ── Process endpoint ──────────────────────────────────────────────────────────
echo ""
echo "=== Process & Metrics ==="
# Warm up with a couple of requests
curl -sf -X POST "http://localhost:$PORT/process" \
  -H 'Content-Type: application/json' -d '{"task":"warmup"}' >/dev/null
curl -sf -X POST "http://localhost:$PORT/process" \
  -H 'Content-Type: application/json' -d '{"task":"warmup2"}' >/dev/null

PROC=$(curl -s -X POST "http://localhost:$PORT/process" \
  -H 'Content-Type: application/json' -d '{"task":"test-task"}')
check "POST /process returns result" \
  "echo '$PROC' | python3 -c \"import sys,json; d=json.load(sys.stdin); assert 'result' in d\""
check "POST /process result contains task name" \
  "echo '$PROC' | python3 -c \"import sys,json; d=json.load(sys.stdin); assert 'test-task' in d['result']\""

METRICS=$(curl -s "http://localhost:$PORT/metrics")
check "GET /metrics returns Prometheus text" \
  "echo '$METRICS' | grep -q 'requests_total'"
check "metrics shows process_ok >= 1" \
  "echo '$METRICS' | grep '^process_ok' | awk '{print \$2}' | python3 -c \"import sys; assert float(sys.stdin.read()) >= 1\""

# ── Fail endpoint ──────────────────────────────────────────────────────────────
echo ""
echo "=== Error Tracking ==="
FAIL_CODE=$(curl -s -o /dev/null -w "%{http_code}" \
  -X POST "http://localhost:$PORT/fail" \
  -H 'Content-Type: application/json' -d '{"reason":"test-error"}')
if [ "$FAIL_CODE" = "500" ]; then pass "POST /fail returns HTTP 500"; else fail "POST /fail returns HTTP 500 (got $FAIL_CODE)"; fi

FAIL_BODY=$(curl -s -X POST "http://localhost:$PORT/fail" \
  -H 'Content-Type: application/json' -d '{"reason":"deliberate"}' || true)
check "POST /fail body contains error field" \
  "echo '$FAIL_BODY' | python3 -c \"import sys,json; d=json.load(sys.stdin); assert 'error' in d\""

METRICS2=$(curl -s "http://localhost:$PORT/metrics")
check "metrics tracks errors (requests_err >= 1)" \
  "echo '$METRICS2' | grep '^requests_err' | awk '{print \$2}' | python3 -c \"import sys; assert float(sys.stdin.read()) >= 1\""

# ── Log volume ─────────────────────────────────────────────────────────────────
echo ""
echo "=== Log Volume ==="
check "log volume was created" \
  "docker volume inspect $VOLUME"

check "app.log exists in volume" \
  "docker run --rm -v $VOLUME:/logs python:3.11-slim \
    python3 -c \"import os; assert os.path.exists('/logs/app.log') and os.path.getsize('/logs/app.log') > 0\""

check "app.log contains valid JSONL" \
  "docker run --rm -v $VOLUME:/logs python:3.11-slim \
    python3 -c \"
import json
with open('/logs/app.log') as f:
    lines = [l for l in f if l.strip()]
assert len(lines) > 0
for l in lines: json.loads(l)
print(f'OK: {len(lines)} valid log entries')
\""

check "app.log records both INFO and ERROR levels" \
  "docker run --rm -v $VOLUME:/logs python:3.11-slim \
    python3 -c \"
import json
with open('/logs/app.log') as f:
    levels = {json.loads(l)['level'] for l in f if l.strip()}
assert 'INFO' in levels and 'ERROR' in levels
\""

# ── Observe profile (sidecars) ─────────────────────────────────────────────────
echo ""
echo "=== Observe Profile (log-watcher + metrics-scraper sidecars) ==="
$COMPOSE --profile observe up -d
echo "  waiting for sidecars to start and scrape..."
sleep 12

check "log-watcher container is running" \
  "docker ps --format '{{.Names}}' | grep -q 'log.watcher\|log_watcher'"

check "metrics-scraper container is running" \
  "docker ps --format '{{.Names}}' | grep -q 'metrics.scraper\|metrics_scraper'"

check "metrics-scraper wrote metrics.jsonl to volume" \
  "docker run --rm -v $VOLUME:/logs python:3.11-slim \
    python3 -c \"import os; assert os.path.exists('/logs/metrics.jsonl') and os.path.getsize('/logs/metrics.jsonl') > 0\""

check "metrics.jsonl contains valid JSONL" \
  "docker run --rm -v $VOLUME:/logs python:3.11-slim \
    python3 -c \"
import json
with open('/logs/metrics.jsonl') as f:
    lines = [l for l in f if l.strip()]
assert len(lines) >= 1
for l in lines: json.loads(l)
print(f'OK: {len(lines)} scraped snapshots')
\""

check "metrics.jsonl entries contain requests_total" \
  "docker run --rm -v $VOLUME:/logs python:3.11-slim \
    python3 -c \"
import json
with open('/logs/metrics.jsonl') as f:
    entry = json.loads(f.readline())
assert 'requests_total' in entry
\""

# ── Debug profile (one-shot debugger) ─────────────────────────────────────────
echo ""
echo "=== Debug Profile (one-shot debugger) ==="
DEBUG_OUT=$($COMPOSE --profile debug run --rm debugger 2>&1)

check "debugger runs to completion" \
  "echo '$DEBUG_OUT' | grep -q 'Report complete'"

check "debugger section 1: finds app health status" \
  "echo '$DEBUG_OUT' | grep -qi 'status.*ok\|ok'"

check "debugger section 2: shows live metrics" \
  "echo '$DEBUG_OUT' | grep -q 'requests_total'"

check "debugger section 3: analyzes log entries" \
  "echo '$DEBUG_OUT' | grep -q 'Total entries'"

check "debugger section 4: reads metrics history from volume" \
  "echo '$DEBUG_OUT' | grep -q 'Snapshots collected'"

# ── Volume/network isolation check ────────────────────────────────────────────
echo ""
echo "=== Isolation ==="
check "log-watcher has no network attachment (volume-only sidecar)" \
  "docker inspect \$(docker ps --format '{{.Names}}' | grep 'log.watcher' | head -1) \
    --format '{{json .NetworkSettings.Networks}}' | \
    python3 -c \"import sys,json; nets=json.load(sys.stdin); assert 'poserforge-sidecar-net' not in nets\""

check "metrics-scraper IS on sidecar network" \
  "docker inspect \$(docker ps --format '{{.Names}}' | grep 'metrics.scraper' | head -1) \
    --format '{{json .NetworkSettings.Networks}}' | \
    python3 -c \"import sys,json; nets=json.load(sys.stdin); assert 'poserforge-sidecar-net' in nets\""

# ── Teardown ──────────────────────────────────────────────────────────────────
echo ""
echo "=== Teardown ==="
$COMPOSE --profile observe --profile debug down -v 2>/dev/null || true

# ── Summary ───────────────────────────────────────────────────────────────────
echo ""
echo "══════════════════════════════════════════"
echo "  Results: $PASS passed, $FAIL failed"
echo "══════════════════════════════════════════"
[ $FAIL -eq 0 ] && echo "  All tests passed." && exit 0 || exit 1
