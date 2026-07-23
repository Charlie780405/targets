#!/usr/bin/env bash
# verify-plan-001e.sh — PLAN-001e 情报生成与周报专项验证
# 用法: bash scripts/verify-plan-001e.sh

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT" || exit 1

pass=0
fail=0

assert_file() {
  local desc="$1" path="$2"
  if [[ -f "$path" ]]; then echo "PASS: $desc"; pass=$((pass+1))
  else echo "FAIL: $desc — 缺少 $path"; fail=$((fail+1)); fi
}

run_check() {
  local desc="$1"; shift
  if "$@" >/dev/null 2>&1; then echo "PASS: $desc"; pass=$((pass+1))
  else echo "FAIL: $desc"; fail=$((fail+1)); fi
}

assert_file "scoring config" "config/scoring.yaml"
assert_file "classify" "apps/processor/classify.py"
assert_file "scoring" "apps/processor/scoring.py"
assert_file "merge" "apps/processor/merge.py"
assert_file "llm_extract" "apps/processor/llm_extract.py"
assert_file "weekly reporter" "apps/reporter/weekly.py"
assert_file "event_extract prompt" "prompts/event_extract.md"
assert_file "weekly_summary prompt" "prompts/weekly_summary.md"
assert_file "test_scoring" "tests/test_scoring.py"
assert_file "test_merge" "tests/test_merge.py"
assert_file "test_weekly_pipeline" "tests/test_weekly_pipeline.py"

if command -v python3 >/dev/null 2>&1; then
  run_check "pytest scoring+merge+weekly" python3 -m pytest -q \
    tests/test_scoring.py tests/test_merge.py tests/test_weekly_pipeline.py
  run_check "ruff check" python3 -m ruff check .
  run_check "mypy packages apps" python3 -m mypy packages apps
else
  echo "SKIP: python3 不可用"
fi

total=$((pass+fail))
echo ""
echo "verify-plan-001e: $pass/$total"
[[ "$fail" -eq 0 ]]
