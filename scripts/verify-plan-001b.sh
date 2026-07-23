#!/usr/bin/env bash
# verify-plan-001b.sh — PLAN-001b ClinicalTrials.gov 采集专项验证
# 用法: bash scripts/verify-plan-001b.sh

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

assert_file "clinicaltrials adapter" "packages/source_adapters/clinicaltrials/adapter.py"
assert_file "clinicaltrials parser" "packages/source_adapters/clinicaltrials/parser.py"
assert_file "trial_diff processor" "apps/processor/trial_diff.py"
assert_file "collector entry" "apps/collector/run_clinicaltrials.py"
assert_file "VCR cassette" "tests/cassettes/clinicaltrials_fetch.yaml"
assert_file "test_clinicaltrials_adapter" "tests/test_clinicaltrials_adapter.py"
assert_file "test_trial_diff" "tests/test_trial_diff.py"

if command -v python3 >/dev/null 2>&1; then
  run_check "pytest clinicaltrials + diff" python3 -m pytest -q \
    tests/test_clinicaltrials_adapter.py tests/test_trial_diff.py
  run_check "ruff check" python3 -m ruff check .
  run_check "mypy packages apps" python3 -m mypy packages apps
else
  echo "SKIP: python3 不可用"
fi

total=$((pass+fail))
echo ""
echo "verify-plan-001b: $pass/$total"
[[ "$fail" -eq 0 ]]
