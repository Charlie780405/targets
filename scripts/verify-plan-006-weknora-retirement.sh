#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."

python3 -m pytest -q \
  tests/test_scheduler.py \
  tests/test_review_workbench.py \
  tests/test_weknora_revoked_gate.py

python3 -m ruff check \
  apps/collector/scheduler.py \
  apps/review_workbench.py \
  apps/review_workbench_ui.py \
  apps/weknora_history.py \
  apps/reporter \
  tests/test_scheduler.py \
  tests/test_review_workbench.py \
  tests/test_weknora_revoked_gate.py

if rg -n 'run_weknora_literature|sync_weknora_literature|WEKNORA_TARGETS_API_KEY|WEKNORA_BASE_URL' apps .env.example; then
  echo 'retired WeKnora ingestion capability is still referenced' >&2
  exit 1
fi

echo 'PASS PLAN-006 WeKnora ingestion retirement'
