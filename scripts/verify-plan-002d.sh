#!/usr/bin/env bash
# verify-plan-002d.sh — PLAN-002d Dashboard 与部署
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT" || exit 1
pass=0; fail=0
check() { local d="$1"; shift; if "$@" >/dev/null 2>&1; then echo "PASS: $d"; pass=$((pass+1)); else echo "FAIL: $d"; fail=$((fail+1)); fi }
assert_file() { [[ -f "$2" ]] && echo "PASS: $1" && pass=$((pass+1)) || { echo "FAIL: $1"; fail=$((fail+1)); }; }

assert_file "dashboard" "apps/reporter/dashboard.py"
assert_file "deploy-production" "scripts/deploy-production.sh"
check "pytest dashboard+weekly" python3 -m pytest -q tests/test_dashboard.py tests/test_weekly_dedup.py

total=$((pass+fail))
echo "verify-plan-002d: $pass/$total"
[[ "$fail" -eq 0 ]]
