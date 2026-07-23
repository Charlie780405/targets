#!/usr/bin/env bash
# verify-plan-001a.sh — PLAN-001a 领域模型与本体专项验证
# 用法: bash scripts/verify-plan-001a.sh

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT" || exit 1

pass=0
fail=0

assert_file() {
  local desc="$1" path="$2"
  if [[ -f "$path" ]]; then echo "PASS: $desc"; pass=$((pass+1))
  else echo "FAIL: $desc — 缺少 $path"; fail=$((fail+1)); fi
}

assert_grep() {
  local desc="$1" pattern="$2" file="$3"
  if grep -qE "$pattern" "$file" 2>/dev/null; then echo "PASS: $desc"; pass=$((pass+1))
  else echo "FAIL: $desc — $file 未匹配 $pattern"; fail=$((fail+1)); fi
}

run_check() {
  local desc="$1"; shift
  if "$@" >/dev/null 2>&1; then echo "PASS: $desc"; pass=$((pass+1))
  else echo "FAIL: $desc"; fail=$((fail+1)); fi
}

# --- 领域模型 ---
assert_file "enums.py" "packages/domain/enums.py"
assert_file "models.py" "packages/domain/models.py"
assert_file "database.py" "packages/domain/database.py"
assert_file "content_hash.py" "packages/domain/content_hash.py"
assert_grep "EventType" "class EventType" "packages/domain/enums.py"
assert_grep "TrialSnapshot" "class TrialSnapshot" "packages/domain/models.py"

# --- 靶点词典 ---
assert_file "target_dictionary.py" "packages/entity_resolution/target_dictionary.py"
assert_file "靶点种子 il4ra.yaml" "config/targets/il4ra.yaml"

# --- Alembic ---
assert_file "alembic.ini" "alembic.ini"
assert_file "migrations/env.py" "migrations/env.py"
assert_file "首版迁移" "migrations/versions/001_initial_schema.py"

# --- 周报模板 ---
assert_file "weekly-brief 模板" "templates/weekly-brief.md.j2"
assert_file "weekly_template 渲染器" "apps/reporter/weekly_template.py"

# --- 测试 ---
assert_file "test_domain_models.py" "tests/test_domain_models.py"
assert_file "test_target_dictionary.py" "tests/test_target_dictionary.py"

# --- 运行时检查（需已 pip install -e '.[dev]'）---
if command -v pytest >/dev/null 2>&1; then
  run_check "pytest 领域与词典测试" python3 -m pytest -q tests/test_domain_models.py tests/test_target_dictionary.py tests/test_weekly_template.py
else
  echo "SKIP: pytest 未安装，跳过运行时测试"
fi

if python3 -m alembic --version >/dev/null 2>&1; then
  TEST_DB="sqlite:////tmp/target_intel_verify_001a.sqlite"
  rm -f /tmp/target_intel_verify_001a.sqlite
  run_check "alembic upgrade head" env DATABASE_URL="$TEST_DB" python3 -m alembic upgrade head
else
  echo "SKIP: alembic 未安装，跳过迁移检查"
fi

if command -v ruff >/dev/null 2>&1; then
  run_check "ruff check" python3 -m ruff check .
else
  echo "SKIP: ruff 未安装"
fi

if command -v mypy >/dev/null 2>&1; then
  run_check "mypy" python3 -m mypy packages apps
else
  echo "SKIP: mypy 未安装"
fi

total=$((pass+fail))
echo ""
echo "verify-plan-001a: $pass/$total"
[[ "$fail" -eq 0 ]]
