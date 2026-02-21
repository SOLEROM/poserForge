#!/usr/bin/env bash
# Integration tests for the Hardware-Aware Runtime pattern.
# Tests both simulation mode (--profile sim) and hardware mode (SENSOR_SOURCE=hw).

set -euo pipefail

COMPOSE="docker compose"

# Load defaults from .env so METRICS_PORT etc. match docker-compose settings
SCRIPT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
if [ -f "$SCRIPT_DIR/.env" ]; then
    set -a; source "$SCRIPT_DIR/.env"; set +a
fi

METRICS_PORT="${METRICS_PORT:-8089}"
URL="http://localhost:${METRICS_PORT}"
PASS=0
FAIL=0

pass() { echo "  PASS [$((PASS+FAIL+1))]: $1"; PASS=$((PASS+1)); }
fail() { echo "  FAIL [$((PASS+FAIL+1))]: $1"; FAIL=$((FAIL+1)); }

# Poll URL until it responds or timeout (seconds) is reached
wait_url() {
    local url="$1" timeout="${2:-90}" i=0
    while [ "$i" -lt "$timeout" ]; do
        curl -sf "$url" >/dev/null 2>&1 && return 0
        sleep 1; i=$((i+1))
    done
    return 1
}

echo "========================================"
echo "  Hardware-Aware Runtime — Test Suite"
echo "========================================"

# ── Cleanup: ensure a pristine starting state ────────────────────────────────
$COMPOSE --profile sim down --remove-orphans -v 2>/dev/null || true

# ── Test 1: Image builds ─────────────────────────────────────────────────────
echo ""
echo "[1] Build image"
if $COMPOSE build --quiet 2>&1; then
    pass "image builds successfully"
else
    fail "image build failed — aborting"
    exit 1
fi

# ── Test 2: Simulation profile starts ────────────────────────────────────────
echo ""
echo "[2] Start simulation profile (simulator + sensor + metrics)"
if $COMPOSE --profile sim up -d; then
    pass "sim profile started"
else
    fail "sim profile failed to start — aborting"
    exit 1
fi

# ── Test 3: Metrics service becomes healthy ───────────────────────────────────
echo ""
echo "[3] Wait for metrics service to become healthy"
if wait_url "$URL/health" 90; then
    pass "metrics service is healthy"
else
    fail "metrics not ready after 90s"
    echo "--- Logs ---"
    $COMPOSE --profile sim logs --tail=30
    $COMPOSE --profile sim down 2>/dev/null || true
    exit 1
fi

# ── Test 4: /health endpoint ──────────────────────────────────────────────────
echo ""
echo "[4] GET /health"
if RESP=$(curl -sf "$URL/health"); then
    if echo "$RESP" | python3 -c "import json,sys; d=json.load(sys.stdin); sys.exit(0 if d.get('status')=='ok' else 1)"; then
        pass "/health returns {status: ok}"
    else
        fail "/health bad response: $RESP"
    fi
else
    fail "curl /health failed"
fi

# ── Test 5: /latest has a sensor reading ─────────────────────────────────────
echo ""
echo "[5] GET /latest"
if RESP=$(curl -sf "$URL/latest"); then
    if echo "$RESP" | python3 -c "
import json, sys
d = json.load(sys.stdin)
sys.exit(0 if all(k in d for k in ('temp_c','pressure_hpa','humidity_pct','ts')) else 1)
"; then
        pass "/latest returns reading with all expected fields"
    else
        fail "/latest missing fields: $RESP"
    fi
else
    fail "curl /latest failed"
fi

# ── Test 6: Source is 'sim' in simulation mode ────────────────────────────────
echo ""
echo "[6] Source field = 'sim'"
if RESP=$(curl -sf "$URL/latest"); then
    if echo "$RESP" | python3 -c "import json,sys; d=json.load(sys.stdin); sys.exit(0 if d.get('source')=='sim' else 1)"; then
        pass "source='sim' in simulation mode"
    else
        fail "source is not 'sim': $RESP"
    fi
else
    fail "curl /latest failed for source check"
fi

# ── Test 7: /history accumulates multiple readings ────────────────────────────
echo ""
echo "[7] /history accumulates readings (waiting 5s for several samples)"
sleep 5
if RESP=$(curl -sf "$URL/history?n=10"); then
    COUNT=$(echo "$RESP" | python3 -c "import json,sys; print(json.load(sys.stdin).get('count',0))" 2>/dev/null || echo 0)
    if [ "$COUNT" -ge 3 ]; then
        pass "/history has $COUNT readings (≥3)"
    else
        fail "/history has only $COUNT readings (expected ≥3)"
    fi
else
    fail "curl /history failed"
fi

# ── Test 8: /stats returns aggregates ────────────────────────────────────────
echo ""
echo "[8] GET /stats"
if RESP=$(curl -sf "$URL/stats"); then
    if echo "$RESP" | python3 -c "
import json, sys
d = json.load(sys.stdin)
ok = (
    d.get('samples', 0) >= 1
    and all(k in d for k in ('temp_c','pressure_hpa','humidity_pct'))
    and all(k in d['temp_c'] for k in ('min','max','avg'))
)
sys.exit(0 if ok else 1)
"; then
        SAMPLES=$(echo "$RESP" | python3 -c "import json,sys; print(json.load(sys.stdin).get('samples',0))")
        pass "/stats returns min/max/avg over $SAMPLES samples"
    else
        fail "/stats bad response: $RESP"
    fi
else
    fail "curl /stats failed"
fi

# ── Test 9: Restart policy is unless-stopped ──────────────────────────────────
echo ""
echo "[9] Restart policy = unless-stopped"
CONTAINER=$($COMPOSE --profile sim ps -q sensor 2>/dev/null | head -1)
if [ -n "$CONTAINER" ]; then
    POLICY=$(docker inspect "$CONTAINER" --format '{{.HostConfig.RestartPolicy.Name}}' 2>/dev/null || echo "")
    if [ "$POLICY" = "unless-stopped" ]; then
        pass "sensor restart policy is 'unless-stopped'"
    else
        fail "restart policy is '$POLICY' (expected 'unless-stopped')"
    fi
else
    fail "could not find sensor container ID"
fi

# ── Test 10: Hardware mode reads from mapped device node ─────────────────────
echo ""
echo "[10] Hardware mode (SENSOR_SOURCE=hw, reads from /dev/hwsensor)"
$COMPOSE --profile sim down 2>/dev/null || true
sleep 2

if SENSOR_SOURCE=hw $COMPOSE up -d && wait_url "$URL/health" 60; then
    sleep 3  # allow at least 3 hw readings to overwrite latest.json
    if RESP=$(curl -sf "$URL/latest"); then
        if echo "$RESP" | python3 -c "import json,sys; d=json.load(sys.stdin); sys.exit(0 if d.get('source')=='hw' else 1)"; then
            pass "hardware mode reads /dev/hwsensor; source='hw'"
        else
            fail "source is not 'hw' in hw mode: $RESP"
        fi
    else
        fail "curl /latest failed in hw mode"
    fi
else
    fail "hardware mode failed to start or metrics not ready"
fi

# ── Cleanup ───────────────────────────────────────────────────────────────────
echo ""
echo "--- Cleanup ---"
$COMPOSE down -v 2>/dev/null || true

echo ""
echo "========================================"
echo "  Results: $PASS passed, $FAIL failed"
echo "========================================"
[ "$FAIL" -eq 0 ]
