#!/usr/bin/env bash
# deploy-production.sh — Vultr 生产部署（git pull + health 容器 + publish）
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

echo "==> git pull origin main"
git pull origin main

echo "==> docker compose health"
docker compose up -d --force-recreate health

echo "==> publish vault (enrich + export)"
python3 -m apps.reporter.publish --vault "${VAULT_PATH:-./vault}" --enrich-publications

echo "==> health check"
curl -sf "http://127.0.0.1:8080/health" | head -c 200
echo ""
echo "deploy-production: OK"
