#!/usr/bin/env bash
# PLAN-004 审阅自动化验证
set +e
pass=0
fail=0

assert_file() {
  local label="$1"
  local path="$2"
  if [[ -f "$path" ]]; then
    echo "PASS $label"
    pass=$((pass + 1))
  else
    echo "FAIL $label missing: $path"
    fail=$((fail + 1))
  fi
}

assert_grep() {
  local label="$1"
  local pattern="$2"
  local path="$3"
  if rg -q "$pattern" "$path" 2>/dev/null; then
    echo "PASS $label"
    pass=$((pass + 1))
  else
    echo "FAIL $label pattern not in $path"
    fail=$((fail + 1))
  fi
}

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

assert_file "vault_publish_pipeline" "apps/reporter/vault_publish_pipeline.py"
assert_file "vault-sync-publish.sh" "scripts/vault-sync-publish.sh"
assert_file "PLAN-004" "docs/plans/PLAN-004-review-automation/PLAN-004-review-automation.md"
assert_grep "vault-sync timer" "target-intel-vault-sync" "scripts/install-vultr-user-systemd.sh"
assert_grep "PUBLISH_USE_LLM" "PUBLISH_USE_LLM" "apps/reporter/vault_publish_pipeline.py"

if command -v pytest >/dev/null 2>&1; then
  if pytest -q tests/test_vault_publish_pipeline.py 2>/dev/null; then
    echo "PASS pytest vault pipeline"
    pass=$((pass + 1))
  else
    echo "FAIL pytest vault pipeline"
    fail=$((fail + 1))
  fi
fi

total=$((pass + fail))
echo "verify-plan-004: $pass/$total"
[[ "$fail" -eq 0 ]]
