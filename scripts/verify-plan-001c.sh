#!/usr/bin/env bash
# verify-plan-001c.sh — PLAN-001c PubMed 采集专项验证
# 用法: bash scripts/verify-plan-001c.sh

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

assert_file "pubmed adapter" "packages/source_adapters/pubmed/adapter.py"
assert_file "pubmed query_builder" "packages/source_adapters/pubmed/query_builder.py"
assert_file "pubmed parser" "packages/source_adapters/pubmed/parser.py"
assert_file "crossref adapter" "packages/source_adapters/crossref/adapter.py"
assert_file "dedup" "packages/entity_resolution/dedup.py"
assert_file "publication_extract" "apps/processor/publication_extract.py"
assert_file "collector run_pubmed" "apps/collector/run_pubmed.py"
assert_file "test_pubmed_adapter" "tests/test_pubmed_adapter.py"
assert_file "test_dedup" "tests/test_dedup.py"

if command -v python3 >/dev/null 2>&1; then
  run_check "pytest pubmed + dedup" python3 -m pytest -q tests/test_pubmed_adapter.py tests/test_dedup.py
  run_check "ruff check" python3 -m ruff check .
  run_check "mypy packages apps" python3 -m mypy packages apps
else
  echo "SKIP: python3 不可用"
fi

total=$((pass+fail))
echo ""
echo "verify-plan-001c: $pass/$total"
[[ "$fail" -eq 0 ]]
