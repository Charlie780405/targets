#!/usr/bin/env bash
# verify-plan-003.sh — PLAN-003 审核队列与研判摘要
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT" || exit 1
pass=0; fail=0
assert_file() { [[ -f "$2" ]] && echo "PASS: $1" && pass=$((pass+1)) || { echo "FAIL: $1"; fail=$((fail+1)); }; }
check() { local d="$1"; shift; if "$@" >/dev/null 2>&1; then echo "PASS: $d"; pass=$((pass+1)); else echo "FAIL: $d"; fail=$((fail+1)); fi }

assert_file "relevance_profile" "config/relevance_profile.yaml"
assert_file "review_queue" "apps/reporter/review_queue.py"
assert_file "approved_digest" "apps/reporter/approved_digest.py"
check "pytest review_queue" python3 -m pytest -q tests/test_review_queue.py

total=$((pass+fail))
echo "verify-plan-003: $pass/$total"
[[ "$fail" -eq 0 ]]
