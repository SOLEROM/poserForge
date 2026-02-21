#!/usr/bin/env bash
# Integration test suite for 5_EnvironmentProfile
# Tests each profile in isolation: no-profile, dev, test, prod
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR/.."

set -a; source .env; set +a

API_PORT="${API_PORT:-8090}"
API_URL="http://localhost:${API_PORT}"

PASS=0
FAIL=0

pass() { echo "  PASS  $1"; PASS=$((PASS+1)); }
fail() { echo "  FAIL  $1${2:+: $2}"; FAIL=$((FAIL+1)); }

http_status() { curl -s -o /dev/null -w "%{http_code}" "$API_URL$1"; }
http_body()   { curl -s "$API_URL$1"; }
json_field()  { python3 -c "import sys,json; print(json.loads(sys.stdin.read()).get('$2',''))"; }

cleanup() {
    docker compose --profile dev --profile test --profile prod \
        down --remove-orphans 2>/dev/null || true
}
trap cleanup EXIT

echo ""
echo "╔══════════════════════════════════════════════════╗"
echo "║    5_EnvironmentProfile — integration tests      ║"
echo "╚══════════════════════════════════════════════════╝"

# ── Test 1: Build ──────────────────────────────────────────────────────────
echo ""
echo "─── 1: Build ───────────────────────────────────────"
docker compose build --quiet \
    && pass "docker compose build succeeds" \
    || { fail "docker compose build failed"; exit 1; }

# ── Test 2: No-profile mode (api only, APP_ENV=development) ───────────────
echo ""
echo "─── 2: No-profile mode (api only) ─────────────────"
APP_ENV=development docker compose up -d
sleep 8

st=$(http_status /health)
[ "$st" = "200" ] && pass "GET /health → 200" || fail "GET /health → 200" "got $st"

env_val=$(http_body /health | json_field - env)
[ "$env_val" = "development" ] \
    && pass "api reports env=development" \
    || fail "api reports env=development" "got '$env_val'"

# profile services must NOT be running
if docker compose ps 2>/dev/null | grep -q "devtools"; then
    fail "devtools absent without --profile dev"
else
    pass "devtools absent without --profile dev"
fi
if docker compose ps 2>/dev/null | grep -q "monitor"; then
    fail "monitor absent without --profile prod"
else
    pass "monitor absent without --profile prod"
fi

docker compose down

# ── Test 3: Dev profile (api + devtools) ──────────────────────────────────
echo ""
echo "─── 3: Dev profile (api + devtools) ───────────────"
APP_ENV=development docker compose --profile dev up -d
sleep 10

st=$(http_status /health)
[ "$st" = "200" ] && pass "GET /health → 200 (dev)" || fail "GET /health → 200 (dev)" "got $st"

env_val=$(http_body /health | json_field - env)
[ "$env_val" = "development" ] \
    && pass "api reports env=development (dev profile)" \
    || fail "api reports env=development (dev profile)" "got '$env_val'"

st=$(http_status /debug)
[ "$st" = "200" ] && pass "GET /debug → 200 in dev mode" || fail "GET /debug → 200 in dev mode" "got $st"

if docker compose --profile dev ps 2>/dev/null | grep -q "devtools"; then
    pass "devtools container running in dev profile"
else
    fail "devtools container running in dev profile"
fi

docker compose --profile dev down

# ── Test 4: Test profile (one-shot tester, APP_ENV=test) ──────────────────
echo ""
echo "─── 4: Test profile (one-shot tester) ─────────────"
APP_ENV=test docker compose --profile test run --rm tester \
    && pass "tester container exits 0" \
    || fail "tester container exits 0" "non-zero exit"

docker compose --profile test down

# ── Test 5: Prod profile (api + monitor) ──────────────────────────────────
echo ""
echo "─── 5: Prod profile (api + monitor) ───────────────"
APP_ENV=production docker compose --profile prod up -d
sleep 10

st=$(http_status /health)
[ "$st" = "200" ] && pass "GET /health → 200 (prod)" || fail "GET /health → 200 (prod)" "got $st"

env_val=$(http_body /health | json_field - env)
[ "$env_val" = "production" ] \
    && pass "api reports env=production" \
    || fail "api reports env=production" "got '$env_val'"

st=$(http_status /debug)
[ "$st" = "403" ] && pass "GET /debug → 403 in prod (blocked)" || fail "GET /debug → 403 in prod (blocked)" "got $st"

st=$(http_status /stats)
[ "$st" = "200" ] && pass "GET /stats → 200 in prod" || fail "GET /stats → 200 in prod" "got $st"

if docker compose --profile prod ps 2>/dev/null | grep -q "monitor"; then
    pass "monitor container running in prod profile"
else
    fail "monitor container running in prod profile"
fi

docker compose --profile prod down

# ── Summary ────────────────────────────────────────────────────────────────
echo ""
echo "══════════════════════════════════════════════════════"
echo "  Results: ${PASS} passed, ${FAIL} failed"
echo "══════════════════════════════════════════════════════"
[ "$FAIL" -eq 0 ] && echo "ALL TESTS PASSED" && exit 0 || { echo "SOME TESTS FAILED"; exit 1; }
