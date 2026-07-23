#!/usr/bin/env bash
# verify-plan-001d.sh — PLAN-001d 公司与投融资采集专项验证
# 用法: bash scripts/verify-plan-001d.sh

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

assert_file "company_ir adapter" "packages/source_adapters/company_ir/adapter.py"
assert_file "sec_edgar adapter" "packages/source_adapters/sec_edgar/adapter.py"
assert_file "asset_resolver" "packages/entity_resolution/asset_resolver.py"
assert_file "org_normalizer" "packages/entity_resolution/org_normalizer.py"
assert_file "source_reliability" "apps/processor/source_reliability.py"
assert_file "company_event_classifier" "apps/processor/company_event_classifier.py"
assert_file "run_companies collector" "apps/collector/run_companies.py"
assert_file "sec_edgar config" "config/sources/sec_edgar.yaml"
assert_file "test_asset_resolver" "tests/test_asset_resolver.py"
assert_file "test_company_adapters" "tests/test_company_adapters.py"

if command -v python3 >/dev/null 2>&1; then
  run_check "pytest asset + company" python3 -m pytest -q tests/test_asset_resolver.py tests/test_company_adapters.py
  run_check "ruff check" python3 -m ruff check .
  run_check "mypy packages apps" python3 -m mypy packages apps
else
  echo "SKIP: python3 不可用"
fi

total=$((pass+fail))
echo ""
echo "verify-plan-001d: $pass/$total"
[[ "$fail" -eq 0 ]]
