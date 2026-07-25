#!/usr/bin/env bash
# verify-plan-002b.sh — PLAN-002b 相关性过滤
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT" || exit 1
pass=0; fail=0
check() { local d="$1"; shift; if "$@" >/dev/null 2>&1; then echo "PASS: $d"; pass=$((pass+1)); else echo "FAIL: $d"; fail=$((fail+1)); fi }
assert_file() { [[ -f "$2" ]] && echo "PASS: $1" && pass=$((pass+1)) || { echo "FAIL: $1"; fail=$((fail+1)); }; }

assert_file "publication_filter.yaml" "config/publication_filter.yaml"
assert_file "publication_relevance" "apps/processor/publication_relevance.py"
check "pytest relevance" python3 -m pytest -q tests/test_publication_relevance.py

total=$((pass+fail))
echo "verify-plan-002b: $pass/$total"
[[ "$fail" -eq 0 ]]
