#!/usr/bin/env bash
# verify-plan-001.sh — PLAN-001 纲领级验证：确认规划与脚手架交付物齐备
# 用法: bash scripts/verify-plan-001.sh

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT" || exit 1

pass=0
fail=0

assert_file() {
  local desc="$1" path="$2"
  if [[ -f "$path" ]]; then echo "PASS: $desc"; pass=$((pass+1))
  else echo "FAIL: $desc — 缺少 $path"; fail=$((fail+1)); fi
}
assert_dir() {
  local desc="$1" path="$2"
  if [[ -d "$path" ]]; then echo "PASS: $desc"; pass=$((pass+1))
  else echo "FAIL: $desc — 缺少目录 $path"; fail=$((fail+1)); fi
}

# --- 顶层工程文件 ---
assert_file "AGENTS.md 存在" "AGENTS.md"
assert_file "README.md 存在" "README.md"
assert_file "pyproject.toml 存在" "pyproject.toml"
assert_file ".env.example 存在" ".env.example"
assert_file ".gitignore 存在" ".gitignore"

# --- agent-context 工作流 ---
assert_file "交付工作流" "docs/agent-context/workflow.md"

# --- 核心规格文档 ---
assert_file "产品规格" "docs/product-spec.md"
assert_file "事件 Schema" "docs/event-schema.md"
assert_file "数据源登记" "docs/source-registry.md"
assert_file "医学审核规则" "docs/medical-review-rules.md"
assert_file "报告风格" "docs/reporting-style.md"

# --- 目录骨架 ---
assert_dir "apps/collector" "apps/collector"
assert_dir "apps/processor" "apps/processor"
assert_dir "apps/reporter" "apps/reporter"
assert_dir "packages/domain" "packages/domain"
assert_dir "packages/source_adapters" "packages/source_adapters"
assert_dir "packages/entity_resolution" "packages/entity_resolution"
assert_dir "packages/obsidian_exporter" "packages/obsidian_exporter"
assert_dir "config/targets" "config/targets"
assert_dir "config/indications" "config/indications"
assert_dir "config/sources" "config/sources"

# --- PLAN 纲领 + 子计划 ---
PD="docs/plans/PLAN-001-target-intel-mvp"
assert_file "纲领目录 README" "$PD/README.md"
assert_file "PLAN-001 纲领" "$PD/PLAN-001-target-intel-mvp.md"
assert_file "PLAN-001a" "$PD/PLAN-001a-domain-ontology.md"
assert_file "PLAN-001b" "$PD/PLAN-001b-trial-collection.md"
assert_file "PLAN-001c" "$PD/PLAN-001c-publication-collection.md"
assert_file "PLAN-001d" "$PD/PLAN-001d-company-finance.md"
assert_file "PLAN-001e" "$PD/PLAN-001e-intelligence-scoring.md"
assert_file "PLAN-001f" "$PD/PLAN-001f-obsidian-ops.md"

# --- 布局校验脚本自身 ---
assert_file "布局校验脚本" "scripts/validate-plan-dir-layout.sh"

total=$((pass+fail))
echo ""
echo "verify-plan-001: $pass/$total"
[[ "$fail" -eq 0 ]]
