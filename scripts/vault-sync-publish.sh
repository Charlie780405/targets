#!/usr/bin/env bash
# Vault 审阅回写闭环：pull → review_sync → LLM publish → push
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
export DATABASE_URL="${DATABASE_URL:-sqlite:////$ROOT/data/target_intel.sqlite}"
exec /usr/bin/python3 -m apps.reporter.vault_publish_pipeline --vault "${VAULT_PATH:-$ROOT/vault}" "$@"
