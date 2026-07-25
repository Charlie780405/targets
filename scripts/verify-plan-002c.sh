#!/usr/bin/env bash
# verify-plan-002c.sh — PLAN-002c LLM 文献分析
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT" || exit 1
pass=0; fail=0
check() { local d="$1"; shift; if "$@" >/dev/null 2>&1; then echo "PASS: $d"; pass=$((pass+1)); else echo "FAIL: $d"; fail=$((fail+1)); fi }
assert_file() { [[ -f "$2" ]] && echo "PASS: $1" && pass=$((pass+1)) || { echo "FAIL: $1"; fail=$((fail+1)); }; }

assert_file "publication_analysis prompt" "prompts/publication_analysis.md"
assert_file "publication_analysis module" "apps/processor/publication_analysis.py"
assert_file "run_publication_enrich" "apps/collector/run_publication_enrich.py"
check "pytest analysis" python3 -m pytest -q tests/test_publication_analysis.py

total=$((pass+fail))
echo "verify-plan-002c: $pass/$total"
[[ "$fail" -eq 0 ]]
