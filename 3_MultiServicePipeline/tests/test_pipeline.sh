#!/usr/bin/env bash
set -e

PASS=0
FAIL=0
BASE="http://localhost:${GATEWAY_PORT:-8088}"

ok()   { echo "  PASS: $1"; PASS=$((PASS+1)); }
fail() { echo "  FAIL: $1"; FAIL=$((FAIL+1)); }

echo "=== MultiServicePipeline Integration Tests ==="
echo "Gateway: $BASE"
echo ""

# ── Pre-flight ────────────────────────────────────────────────────────────────
if ! curl -sf "$BASE/health" >/dev/null 2>&1; then
    echo "ERROR: Gateway not responding at $BASE"
    echo "       Run 'make up' first."
    exit 1
fi

# ── Test 1: Gateway health ────────────────────────────────────────────────────
echo "1. Gateway /health"
STATUS=$(curl -sf "$BASE/health" \
    | python3 -c "import sys,json; print(json.load(sys.stdin)['status'])")
[ "$STATUS" = "ok" ] \
    && ok "gateway returns status=ok" \
    || fail "gateway /health returned unexpected: $STATUS"

# ── Test 2: Submit a job ──────────────────────────────────────────────────────
echo "2. Submit job — nine unique words"
TEXT="The quick brown fox jumps over the lazy dog"
RESP=$(curl -sf -X POST "$BASE/submit" \
    -H 'Content-Type: application/json' \
    -d "{\"text\":\"$TEXT\"}")
JOB_ID=$(echo "$RESP" | python3 -c "import sys,json; print(json.load(sys.stdin)['job_id'])")
[ -n "$JOB_ID" ] \
    && ok "submit returned job_id=$JOB_ID" \
    || fail "submit did not return a job_id"

# ── Test 3: Result is available (pipeline is synchronous) ─────────────────────
echo "3. Result available for job"
RESULT=$(curl -sf "$BASE/result/$JOB_ID" 2>/dev/null)
[ -n "$RESULT" ] \
    && ok "result found for job_id=$JOB_ID" \
    || fail "result not found for job_id=$JOB_ID"

# ── Test 4: total_words ───────────────────────────────────────────────────────
echo "4. total_words = 9"
TOTAL=$(echo "$RESULT" | python3 -c "import sys,json; print(json.load(sys.stdin)['total_words'])")
[ "$TOTAL" = "9" ] \
    && ok "total_words=9 (correct)" \
    || fail "total_words=$TOTAL (expected 9)"

# ── Test 5: unique_words ──────────────────────────────────────────────────────
echo "5. unique_words = 8  (\"the\" appears twice)"
UNIQUE=$(echo "$RESULT" | python3 -c "import sys,json; print(json.load(sys.stdin)['unique_words'])")
[ "$UNIQUE" = "8" ] \
    && ok "unique_words=8 (correct)" \
    || fail "unique_words=$UNIQUE (expected 8)"

# ── Test 6: top word ──────────────────────────────────────────────────────────
echo "6. Top word is \"the\" (2 occurrences)"
TOP=$(echo "$RESULT" | python3 -c "import sys,json; print(json.load(sys.stdin)['top_words'][0][0])")
[ "$TOP" = "the" ] \
    && ok "top word is 'the'" \
    || fail "top word is '$TOP' (expected 'the')"

# ── Test 7: Repeated-word job ─────────────────────────────────────────────────
echo "7. Submit job with repeated words"
RESP2=$(curl -sf -X POST "$BASE/submit" \
    -H 'Content-Type: application/json' \
    -d '{"text":"hello hello world world world"}')
JOB_ID2=$(echo "$RESP2" | python3 -c "import sys,json; print(json.load(sys.stdin)['job_id'])")
RESULT2=$(curl -sf "$BASE/result/$JOB_ID2")
TOP2=$(echo "$RESULT2" | python3 -c "import sys,json; print(json.load(sys.stdin)['top_words'][0][0])")
[ "$TOP2" = "world" ] \
    && ok "top word is 'world' (3 occurrences)" \
    || fail "top word is '$TOP2' (expected 'world')"

# ── Test 8: Punctuation stripped by normalize ─────────────────────────────────
echo "8. Punctuation is stripped (normalize stage)"
RESP3=$(curl -sf -X POST "$BASE/submit" \
    -H 'Content-Type: application/json' \
    -d '{"text":"Hello, world! Hello... world."}')
JOB_ID3=$(echo "$RESP3" | python3 -c "import sys,json; print(json.load(sys.stdin)['job_id'])")
RESULT3=$(curl -sf "$BASE/result/$JOB_ID3")
TOTAL3=$(echo "$RESULT3" | python3 -c "import sys,json; print(json.load(sys.stdin)['total_words'])")
[ "$TOTAL3" = "4" ] \
    && ok "punctuation stripped → total_words=4" \
    || fail "total_words=$TOTAL3 after punctuation strip (expected 4)"

# ── Test 9: Unknown job_id returns 404 ────────────────────────────────────────
echo "9. Unknown job_id → 404"
CODE=$(curl -s -o /dev/null -w "%{http_code}" "$BASE/result/no-such-job-id")
[ "$CODE" = "404" ] \
    && ok "unknown job_id returns 404" \
    || fail "unknown job_id returned HTTP $CODE (expected 404)"

# ── Test 10: Empty text returns 400 ──────────────────────────────────────────
echo "10. Empty text → 400"
CODE=$(curl -s -o /dev/null -w "%{http_code}" -X POST "$BASE/submit" \
    -H 'Content-Type: application/json' -d '{"text":""}')
[ "$CODE" = "400" ] \
    && ok "empty text returns 400" \
    || fail "empty text returned HTTP $CODE (expected 400)"

# ── Summary ───────────────────────────────────────────────────────────────────
echo ""
echo "Results: $PASS passed, $FAIL failed"
[ "$FAIL" = "0" ]
