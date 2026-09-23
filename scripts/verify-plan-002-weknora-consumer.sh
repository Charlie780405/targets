#!/usr/bin/env bash
set -euo pipefail

passed=0
total=0

run_check() {
  total=$((total + 1))
  local name="$1"
  shift
  if "$@"; then
    passed=$((passed + 1))
    printf '[PASS] %s\n' "$name"
  else
    printf '[FAIL] %s\n' "$name" >&2
    exit 1
  fi
}

run_check 'WeKnora consumer tests' python3 -m pytest -q tests/test_weknora_literature.py
run_check 'WeKnora consumer ruff' python3 -m ruff check \
  apps/collector/weknora_literature.py \
  apps/collector/run_weknora_literature.py \
  packages/domain/models.py \
  apps/reporter/publish.py \
  apps/reporter/review_sync.py \
  tests/test_weknora_literature.py

verify_tmp="$(mktemp -d)"
export DATABASE_URL="sqlite:///${verify_tmp}/target-intel.sqlite"
run_check 'Alembic upgrade with projection' alembic upgrade head
run_check 'Alembic downgrade preserves prior schema' alembic downgrade 62cca6f53ae0
run_check 'Alembic upgrade is replayable' alembic upgrade head

printf 'PLAN-002 WeKnora consumer: %d/%d checks passed\n' "$passed" "$total"
