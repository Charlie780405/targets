#!/usr/bin/env bash
# verify-plan-001f.sh — PLAN-001f Obsidian 与运行保障专项验证
# 用法: bash scripts/verify-plan-001f.sh

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

assert_file "obsidian exporter" "packages/obsidian_exporter/exporter.py"
assert_file "vault layout" "packages/obsidian_exporter/vault_layout.py"
assert_file "publish" "apps/reporter/publish.py"
assert_file "review_sync" "apps/reporter/review_sync.py"
assert_file "metrics" "apps/processor/metrics.py"
assert_file "health" "apps/health.py"
assert_file "collector health" "apps/collector/health.py"
assert_file "reporter health" "apps/reporter/health.py"
assert_file "collect service" "scripts/schedule/target-intel-collect.service"
assert_file "collect timer" "scripts/schedule/target-intel-collect.timer"
assert_file "weekly service" "scripts/schedule/target-intel-weekly.service"
assert_file "weekly timer" "scripts/schedule/target-intel-weekly.timer"
assert_file "docker-compose" "docker-compose.yml"
assert_file "test_obsidian_exporter" "tests/test_obsidian_exporter.py"
assert_file "test_review_sync" "tests/test_review_sync.py"
assert_file "test_ops" "tests/test_ops.py"

if command -v python3 >/dev/null 2>&1; then
  run_check "pytest obsidian+ops" python3 -m pytest -q \
    tests/test_obsidian_exporter.py tests/test_review_sync.py tests/test_ops.py
  run_check "verify-plan-001e regression" bash scripts/verify-plan-001e.sh
  run_check "ruff check" python3 -m ruff check .
  run_check "mypy packages apps" python3 -m mypy packages apps
else
  echo "SKIP: python3 不可用"
fi

total=$((pass+fail))
echo ""
echo "verify-plan-001f: $pass/$total"
[[ "$fail" -eq 0 ]]
