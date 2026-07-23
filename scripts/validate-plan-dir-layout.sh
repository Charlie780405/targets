#!/usr/bin/env bash
# validate-plan-dir-layout.sh — 校验 PLAN 目录规范
# 规则：所有 PLAN 放 docs/plans/PLAN-XXX-<slug>/ 内；根目录禁止散落 PLAN-*.md
# 用法: bash scripts/validate-plan-dir-layout.sh

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT" || exit 1

pass=0
fail=0

check() {
  local desc="$1"; shift
  if "$@"; then echo "PASS: $desc"; pass=$((pass+1)); else echo "FAIL: $desc"; fail=$((fail+1)); fi
}

# 1. docs/plans 根目录不得有散落的 PLAN-*.md
no_stray_plans() {
  local stray
  stray=$(find docs/plans -maxdepth 1 -name 'PLAN-*.md' 2>/dev/null)
  [[ -z "$stray" ]]
}
check "docs/plans 根目录无散落 PLAN-*.md" no_stray_plans

# 2. 每个 PLAN 目录须匹配 PLAN-XXX-<slug>
dirs_named_ok() {
  local bad="" d
  for d in docs/plans/PLAN-*/; do
    [[ -d "$d" ]] || continue
    base=$(basename "$d")
    [[ "$base" =~ ^PLAN-[0-9]+-[a-z0-9-]+$ ]] || bad="$bad $base"
  done
  [[ -z "$bad" ]] || { echo "  非法目录名:$bad"; return 1; }
}
check "PLAN 目录名符合 PLAN-XXX-<slug>" dirs_named_ok

# 3. 每个 PLAN 目录须含同名纲领文件
dirs_have_master() {
  local bad="" d
  for d in docs/plans/PLAN-*/; do
    [[ -d "$d" ]] || continue
    base=$(basename "$d")
    [[ -f "$d/$base.md" ]] || bad="$bad $base"
  done
  [[ -z "$bad" ]] || { echo "  缺纲领文件:$bad"; return 1; }
}
check "每个 PLAN 目录含同名纲领 .md" dirs_have_master

total=$((pass+fail))
echo ""
echo "validate-plan-dir-layout: $pass/$total"
[[ "$fail" -eq 0 ]]
