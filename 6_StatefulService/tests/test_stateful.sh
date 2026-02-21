#!/usr/bin/env bash
# Integration tests for 6_StatefulService
# Demonstrates: sessions survive restart, rebuild, and crash.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
set -a; source "$SCRIPT_DIR/.env"; set +a

PORT="${APP_PORT:-8091}"
BASE="http://localhost:${PORT}"
COMPOSE="docker compose"
PASS=0
FAIL=0

pass() { echo "  PASS  $1"; PASS=$((PASS+1)); }
fail() { echo "  FAIL  $1"; FAIL=$((FAIL+1)); }

wait_healthy() {
    local n=0
    echo -n "  waiting for service"
    while ! curl -sf "$BASE/health" >/dev/null 2>&1; do
        sleep 1; n=$((n+1))
        echo -n "."
        [ $n -lt 40 ] || { echo " timed out"; exit 1; }
    done
    echo " ready"
}

echo
echo "=== 6_StatefulService Integration Tests ==="
echo

# ── Setup ──────────────────────────────────────────────────────────────────────
echo "--- Setup: build and start service ---"
$COMPOSE up -d --build
wait_healthy
echo

# ── Test 1: health check ───────────────────────────────────────────────────────
echo "--- Test 1: health check ---"
resp=$(curl -sf "$BASE/health")
echo "$resp" | grep -q '"status":"ok"' \
    && pass "health returns ok" || fail "health check failed"

# ── Test 2: startup_count persisted from first boot ───────────────────────────
echo "--- Test 2: startup_count >= 1 ---"
resp=$(curl -sf "$BASE/state")
echo "$resp" | python3 -c "import sys,json; d=json.load(sys.stdin); assert d['startup_count'] >= 1" \
    && pass "startup_count >= 1" || fail "startup_count missing or zero"

# ── Test 3: create a session ──────────────────────────────────────────────────
echo "--- Test 3: create session ---"
resp=$(curl -sf -X POST "$BASE/sessions" \
    -H "Content-Type: application/json" \
    -d '{"name":"demo-session","data":{"env":"test"}}')
SID=$(echo "$resp" | python3 -c "import sys,json; print(json.load(sys.stdin)['id'])")
echo "$resp" | grep -q '"name":"demo-session"' \
    && pass "session created (id=${SID:0:8}…)" || fail "session creation failed"

# ── Test 4: list sessions includes new session ─────────────────────────────────
echo "--- Test 4: list sessions includes new session ---"
resp=$(curl -sf "$BASE/sessions")
echo "$resp" | grep -q "$SID" \
    && pass "session appears in list" || fail "session not in list"

# ── Test 5: get session by ID ──────────────────────────────────────────────────
echo "--- Test 5: get session by ID ---"
resp=$(curl -sf "$BASE/sessions/$SID")
echo "$resp" | grep -q '"name":"demo-session"' \
    && pass "get session returns correct data" || fail "get session failed"

# ── Test 6: update session increments access_count ────────────────────────────
echo "--- Test 6: update session ---"
resp=$(curl -sf -X PUT "$BASE/sessions/$SID" \
    -H "Content-Type: application/json" \
    -d '{"data":{"env":"updated"}}')
COUNT=$(echo "$resp" | python3 -c "import sys,json; print(json.load(sys.stdin)['access_count'])")
[ "$COUNT" -ge 1 ] \
    && pass "access_count incremented to $COUNT" || fail "access_count not incremented"

# ── Test 7: session survives container restart ─────────────────────────────────
echo "--- Test 7: session survives container restart ---"
$COMPOSE restart app
wait_healthy
resp=$(curl -sf "$BASE/sessions/$SID")
echo "$resp" | grep -q '"name":"demo-session"' \
    && pass "session survives restart" || fail "session lost on restart"

# ── Test 8: container_id changes after restart ────────────────────────────────
echo "--- Test 8: container_id changes after restart ---"
CID1=$(curl -sf "$BASE/state" | python3 -c "import sys,json; print(json.load(sys.stdin)['container_id'])")
$COMPOSE restart app
wait_healthy
CID2=$(curl -sf "$BASE/state" | python3 -c "import sys,json; print(json.load(sys.stdin)['container_id'])")
[ "$CID1" != "$CID2" ] \
    && pass "container_id changed ($CID1 → $CID2)" || fail "container_id unchanged"

# ── Test 9: startup_count increments on each start ───────────────────────────
echo "--- Test 9: startup_count increments on restart ---"
SC=$(curl -sf "$BASE/state" | python3 -c "import sys,json; print(json.load(sys.stdin)['startup_count'])")
[ "$SC" -ge 2 ] \
    && pass "startup_count=$SC (>= 2, proves persisted counter)" || fail "startup_count not incrementing"

# ── Test 10: crash → auto-restart → sessions survive ─────────────────────────
echo "--- Test 10: crash-and-recover preserves sessions ---"
curl -sf -X POST "$BASE/crash" >/dev/null 2>&1 || true   # service will exit(1)
sleep 5   # Docker's restart: unless-stopped kicks in
wait_healthy
resp=$(curl -sf "$BASE/sessions/$SID")
echo "$resp" | grep -q '"name":"demo-session"' \
    && pass "session survives crash + auto-restart" || fail "session lost after crash"

# ── Test 11: crash_count incremented ─────────────────────────────────────────
echo "--- Test 11: crash_count incremented ---"
CC=$(curl -sf "$BASE/state" | python3 -c "import sys,json; print(json.load(sys.stdin)['crash_count'])")
[ "$CC" -ge 1 ] \
    && pass "crash_count=$CC (>= 1)" || fail "crash_count not incremented"

# ── Test 12: events log has startup entries ────────────────────────────────────
echo "--- Test 12: events log has startup entries ---"
resp=$(curl -sf "$BASE/events")
echo "$resp" | grep -q '"startup"' \
    && pass "events contain startup entries" || fail "no startup events found"

# ── Test 13: inspector reads volume without HTTP ──────────────────────────────
echo "--- Test 13: inspector works with service stopped ---"
$COMPOSE down
out=$($COMPOSE --profile inspect run --rm inspector 2>&1)
echo "$out" | grep -q "SESSIONS" \
    && pass "inspector reads volume without service" || fail "inspector failed"
# Restart for remaining tests
$COMPOSE up -d
wait_healthy

# ── Test 14: delete session ───────────────────────────────────────────────────
echo "--- Test 14: delete session ---"
resp=$(curl -sf -X DELETE "$BASE/sessions/$SID")
echo "$resp" | grep -q '"deleted"' \
    && pass "session deleted" || fail "session delete failed"

# ── Test 15: named volume exists ──────────────────────────────────────────────
echo "--- Test 15: named volume exists ---"
docker volume ls --format "{{.Name}}" | grep -q "poserforge-stateful-data" \
    && pass "named volume poserforge-stateful-data exists" || fail "named volume missing"

# ── Results ────────────────────────────────────────────────────────────────────
echo
echo "══════════════════════════════════════════"
echo "  Results: ${PASS} passed, ${FAIL} failed"
echo "══════════════════════════════════════════"
echo

[ "$FAIL" -eq 0 ]
