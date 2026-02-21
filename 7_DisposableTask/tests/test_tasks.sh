#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
COMPOSE_DIR="$(dirname "$SCRIPT_DIR")"
PASS=0
FAIL=0
VOLUME="poserforge-task-data"

cd "$COMPOSE_DIR"

# Helper: run python snippet against the shared volume
inspect() {
    docker run --rm -v "$VOLUME:/data" python:3.11-slim python -c "$1" 2>/dev/null | tail -1
}

pass() { echo "  PASS: $1"; PASS=$((PASS+1)); }
fail() { echo "  FAIL: $1"; FAIL=$((FAIL+1)); }

echo "=== 7_DisposableTask Integration Tests ==="
echo ""

# Setup: clean slate — let compose create the volume on first run
echo "[setup] Resetting data volume..."
docker volume rm "$VOLUME" 2>/dev/null || true

# ── Test 1: seed exits 0 ────────────────────────────────────────────────────
echo "Test 1: seed exits 0"
if docker compose run --rm seed; then
    pass "seed exits 0"
else
    fail "seed exits 0"
fi

# ── Test 2: records.json has 20 records ─────────────────────────────────────
echo "Test 2: records.json has 20 records"
N=$(inspect "import json; print(len(json.load(open('/data/records.json'))))")
if [ "$N" = "20" ]; then
    pass "20 records seeded"
else
    fail "20 records (got: $N)"
fi

# ── Test 3: schema_version is v1 ────────────────────────────────────────────
echo "Test 3: schema_version is v1"
VER=$(inspect "print(open('/data/schema_version').read().strip())")
if [ "$VER" = "v1" ]; then
    pass "schema is v1"
else
    fail "schema is v1 (got: $VER)"
fi

# ── Test 4: seed is idempotent ───────────────────────────────────────────────
echo "Test 4: seed idempotent (no duplicate records on re-run)"
docker compose run --rm seed >/dev/null 2>&1
N2=$(inspect "import json; print(len(json.load(open('/data/records.json'))))")
if [ "$N2" = "20" ]; then
    pass "seed idempotent, still 20 records"
else
    fail "seed idempotent (got: $N2 records after 2nd run)"
fi

# ── Test 5: migrate exits 0 ──────────────────────────────────────────────────
echo "Test 5: migrate exits 0"
if docker compose run --rm migrate; then
    pass "migrate exits 0"
else
    fail "migrate exits 0"
fi

# ── Test 6: schema_version is v2 ────────────────────────────────────────────
echo "Test 6: schema_version is v2"
VER=$(inspect "print(open('/data/schema_version').read().strip())")
if [ "$VER" = "v2" ]; then
    pass "schema is v2"
else
    fail "schema is v2 (got: $VER)"
fi

# ── Test 7: records have category + normalized_value fields ─────────────────
echo "Test 7: category and normalized_value fields added"
HAS=$(inspect "import json; d=json.load(open('/data/records.json')); print(all('category' in r and 'normalized_value' in r for r in d))")
if [ "$HAS" = "True" ]; then
    pass "category + normalized_value present in all records"
else
    fail "category + normalized_value present (got: $HAS)"
fi

# ── Test 8: migrate is idempotent ───────────────────────────────────────────
echo "Test 8: migrate idempotent (re-run safe)"
if docker compose run --rm migrate; then
    pass "migrate idempotent exits 0"
else
    fail "migrate idempotent exits 0"
fi
VER=$(inspect "print(open('/data/schema_version').read().strip())")
if [ "$VER" = "v2" ]; then
    pass "schema still v2 after re-migrate"
else
    fail "schema still v2 after re-migrate (got: $VER)"
fi

# ── Test 9: analyze exits 0 ──────────────────────────────────────────────────
echo "Test 9: analyze exits 0"
if docker compose run --rm analyze; then
    pass "analyze exits 0"
else
    fail "analyze exits 0"
fi

# ── Test 10: report.json created with correct total ─────────────────────────
echo "Test 10: report.json has total_records == 20"
TOTAL=$(inspect "import json; print(json.load(open('/data/report.json'))['total_records'])")
if [ "$TOTAL" = "20" ]; then
    pass "report total_records=20"
else
    fail "report total_records (got: $TOTAL)"
fi

# ── Test 11: report has by_category breakdown ───────────────────────────────
echo "Test 11: report has by_category breakdown"
HAS_CAT=$(inspect "import json; r=json.load(open('/data/report.json')); print('by_category' in r and len(r['by_category']) > 0)")
if [ "$HAS_CAT" = "True" ]; then
    pass "by_category present in report"
else
    fail "by_category present in report (got: $HAS_CAT)"
fi

# ── Test 12: cleanup exits 0 ────────────────────────────────────────────────
echo "Test 12: cleanup exits 0"
if docker compose run --rm cleanup; then
    pass "cleanup exits 0"
else
    fail "cleanup exits 0"
fi

# ── Test 13: record count decreased (5 old records removed) ─────────────────
echo "Test 13: old records removed by cleanup"
N_AFTER=$(inspect "import json; print(len(json.load(open('/data/records.json'))))")
if [ "$N_AFTER" -lt "20" ]; then
    pass "records reduced from 20 to $N_AFTER"
else
    fail "records should be < 20 after cleanup (got: $N_AFTER)"
fi

# ── Test 14: export exits 0 ──────────────────────────────────────────────────
echo "Test 14: export exits 0"
if docker compose run --rm export; then
    pass "export exits 0"
else
    fail "export exits 0"
fi

# ── Test 15: export.csv has correct headers and row count ───────────────────
echo "Test 15: export.csv headers and row count"
HEADERS=$(inspect "print(open('/data/export.csv').readline().strip())")
ROWS=$(inspect "print(len(open('/data/export.csv').readlines()) - 1)")  # subtract header
if echo "$HEADERS" | grep -q "id" && echo "$HEADERS" | grep -q "name" && echo "$HEADERS" | grep -q "value" && [ "$ROWS" = "$N_AFTER" ]; then
    pass "export.csv headers OK, $ROWS rows match record count"
else
    fail "export.csv (headers: $HEADERS, rows: $ROWS, expected: $N_AFTER)"
fi

echo ""
echo "=== Results: $PASS passed, $FAIL failed ==="
[ "$FAIL" -eq 0 ]
