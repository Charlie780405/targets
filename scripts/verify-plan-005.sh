#!/usr/bin/env bash
# PLAN-005：WeKnora 来源失效后的发布门禁
set -euo pipefail
cd "$(dirname "$0")/.."
python3 -m pytest tests/test_weknora_revoked_gate.py tests/test_weknora_literature.py tests/test_review_workbench.py -q
ruff check apps/collector/weknora_literature.py apps/reporter tests/test_weknora_revoked_gate.py
echo "PASS PLAN-005 verify"
