#!/usr/bin/env bash
# verify-plan-002.sh — PLAN-002 文献质量与研判（纲领）
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT" || exit 1
pass=0; fail=0

for script in verify-plan-002a verify-plan-002b verify-plan-002c verify-plan-002d; do
  if bash "$ROOT/scripts/${script}.sh"; then
    echo "PASS: $script"
    pass=$((pass+1))
  else
    echo "FAIL: $script"
    fail=$((fail+1))
  fi
done

if bash "$ROOT/scripts/validate-plan-dir-layout.sh" >/dev/null 2>&1; then
  echo "PASS: validate-plan-dir-layout"
  pass=$((pass+1))
else
  echo "FAIL: validate-plan-dir-layout"
  fail=$((fail+1))
fi

total=$((pass+fail))
echo "verify-plan-002: $pass/$total"
[[ "$fail" -eq 0 ]]
