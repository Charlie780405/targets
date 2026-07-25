#!/usr/bin/env bash
# verify-plan-002a.sh — PLAN-002a 富导出
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT" || exit 1
pass=0; fail=0
check() { local d="$1"; shift; if "$@" >/dev/null 2>&1; then echo "PASS: $d"; pass=$((pass+1)); else echo "FAIL: $d"; fail=$((fail+1)); fi }
assert_file() { [[ -f "$2" ]] && echo "PASS: $1" && pass=$((pass+1)) || { echo "FAIL: $1"; fail=$((fail+1)); }; }

assert_file "publication_context" "packages/obsidian_exporter/publication_context.py"
assert_file "review_sync cli" "apps/reporter/review_sync.py"
run_pytest() { python3 -m pytest -q "$@"; }
check "pytest publication export tests" run_pytest tests/test_publication_export.py tests/test_review_sync.py

total=$((pass+fail))
echo "verify-plan-002a: $pass/$total"
[[ "$fail" -eq 0 ]]
