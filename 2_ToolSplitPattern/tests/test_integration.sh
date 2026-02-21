#!/usr/bin/env bash
# Integration test: Service + Tool Split Pattern
# Verifies the daemon starts, tools communicate with it, and shared volume works.

set -euo pipefail

# Run from the project root so docker compose picks up docker-compose.yml and .env
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "${SCRIPT_DIR}/.."

# Load API_PORT from .env so shell-level URL matches what Compose exposes on the host
API_PORT=$(grep '^API_PORT=' .env 2>/dev/null | cut -d= -f2 | tr -d '[:space:]')
API_PORT=${API_PORT:-8088}

COMPOSE="docker compose"
API_URL="http://localhost:${API_PORT}"
PASS=0; FAIL=0

# ── Helpers ───────────────────────────────────────────────────────────────────
ok()   { echo "  [PASS] $*"; PASS=$((PASS+1)); }
fail() { echo "  [FAIL] $*"; FAIL=$((FAIL+1)); }
header() { echo; echo "─── $* ───"; }

wait_healthy() {
  local max=20 i=0
  while (( i < max )); do
    curl -sf "${API_URL}/health" > /dev/null 2>&1 && return 0
    (( i++ )) || true
    sleep 1
  done
  return 1
}

# ── Setup ─────────────────────────────────────────────────────────────────────
header "Setup: clean slate"
$COMPOSE down -v --remove-orphans 2>/dev/null || true
$COMPOSE build --quiet

# ── Test 1: Start service ──────────────────────────────────────────────────────
header "Test 1: Service starts and becomes healthy"
$COMPOSE up -d api
if wait_healthy; then
  ok "Service healthy at ${API_URL}/health"
else
  fail "Service did not become healthy"
  $COMPOSE logs api
  exit 1
fi

# ── Test 2: Submit tool ────────────────────────────────────────────────────────
header "Test 2: Submit tool creates jobs"
out1=$($COMPOSE run --rm -e JOB_NAME="batch-1" -e JOB_CMD="echo batch1" submit 2>&1)
echo "$out1"
if echo "$out1" | grep -q '"status": "pending"'; then
  ok "submit tool returned pending job"
else
  fail "submit tool did not return expected output"
fi

# Submit two more jobs
$COMPOSE run --rm -e JOB_NAME="batch-2" -e JOB_CMD="echo batch2" submit > /dev/null
$COMPOSE run --rm -e JOB_NAME="batch-3" -e JOB_CMD="ls /workspace"  submit > /dev/null
ok "3 jobs submitted"

# ── Test 3: Query tool lists jobs ─────────────────────────────────────────────
header "Test 3: Query tool lists all jobs"
out2=$($COMPOSE run --rm query 2>&1)
echo "$out2"
if echo "$out2" | grep -q '"count": 3'; then
  ok "query tool reports 3 jobs"
else
  fail "query tool count mismatch"
fi

# ── Test 4: Service persists to shared volume ──────────────────────────────────
header "Test 4: Shared volume contains jobs.json"
# Read file directly via a bare container (same volume, no service involved)
vol_out=$(docker run --rm \
  -v poserforge-workspace:/workspace \
  python:3.11-slim \
  python -c "import json,pathlib; d=json.loads(pathlib.Path('/workspace/jobs.json').read_text()); print(len(d))")
if [[ "$vol_out" == "3" ]]; then
  ok "jobs.json on shared volume contains 3 records"
else
  fail "jobs.json record count: expected 3, got ${vol_out}"
fi

# ── Test 5: Report tool reads volume directly ─────────────────────────────────
header "Test 5: Report tool reads shared volume"
out3=$($COMPOSE run --rm report 2>&1)
echo "$out3"
if echo "$out3" | grep -q "Total jobs  : 3"; then
  ok "report tool shows 3 total jobs"
else
  fail "report tool output unexpected"
fi

# ── Test 6: Tool containers exit cleanly ──────────────────────────────────────
header "Test 6: Tool containers are not running (one-shot lifecycle)"
# Scope to this project's network — avoids catching containers from other projects
running=$(docker ps --filter "network=poserforge-toolnet" --format "{{.Names}}" | grep -v "poserforge-api" || true)
if [[ -z "$running" ]]; then
  ok "no lingering tool containers"
else
  fail "unexpected running containers: ${running}"
fi

# ── Test 7: Service still running after all tools finished ────────────────────
header "Test 7: Daemon still running after tool workload"
if curl -sf "${API_URL}/health" > /dev/null; then
  ok "service still healthy"
else
  fail "service went down"
fi

# ── Teardown ──────────────────────────────────────────────────────────────────
header "Teardown"
$COMPOSE down -v --remove-orphans

# ── Summary ───────────────────────────────────────────────────────────────────
echo
echo "════════════════════════════════════════"
echo "  Results: ${PASS} passed, ${FAIL} failed"
echo "════════════════════════════════════════"
[[ $FAIL -eq 0 ]]
