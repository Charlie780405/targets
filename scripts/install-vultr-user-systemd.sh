#!/usr/bin/env bash
# 在 Vultr 上以 dev 用户安装 systemd user timer（无需 root）
# 用法: bash scripts/install-vultr-user-systemd.sh

set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
UNIT_DIR="${XDG_CONFIG_HOME:-$HOME/.config}/systemd/user"
mkdir -p "$UNIT_DIR"

write_unit() {
  local name="$1"
  local content="$2"
  printf '%s\n' "$content" > "$UNIT_DIR/$name"
}

write_unit target-intel-collect.service "[Unit]
Description=Target Intelligence — 多源采集（CT.gov / PubMed / 公司）
After=network-online.target

[Service]
Type=oneshot
WorkingDirectory=$ROOT
Environment=DATABASE_URL=sqlite:////$ROOT/data/target_intel.sqlite
EnvironmentFile=-$ROOT/.env
ExecStart=/usr/bin/python3 -m apps.collector.run_clinicaltrials --init-db
ExecStart=/usr/bin/python3 -m apps.collector.run_pubmed
ExecStart=/usr/bin/python3 -m apps.collector.run_companies
# LLM 摘要（首次部署执行一次：pip install 'openai>=1.30' --break-system-packages）
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=default.target
"

write_unit target-intel-collect.timer "[Unit]
Description=Target Intelligence — 每日采集（北京时间 06:00 = UTC 22:00）

[Timer]
# 主机 systemd 默认 UTC；22:00 UTC = 次日北京时间 06:00
OnCalendar=*-*-* 22:00:00
Persistent=true
RandomizedDelaySec=300

[Install]
WantedBy=timers.target
"

write_unit target-intel-weekly.service "[Unit]
Description=Target Intelligence — 周报生成与 Vault 发布
After=network-online.target

[Service]
Type=oneshot
WorkingDirectory=$ROOT
Environment=DATABASE_URL=sqlite:////$ROOT/data/target_intel.sqlite
EnvironmentFile=-$ROOT/.env
ExecStart=/bin/bash $ROOT/scripts/vault-sync-publish.sh --force
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=default.target
"

write_unit target-intel-vault-sync.service "[Unit]
Description=Target Intelligence — Vault 审阅 pull + review_sync + LLM publish
After=network-online.target

[Service]
Type=oneshot
WorkingDirectory=$ROOT
Environment=DATABASE_URL=sqlite:////$ROOT/data/target_intel.sqlite
EnvironmentFile=-$ROOT/.env
ExecStart=/bin/bash $ROOT/scripts/vault-sync-publish.sh
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=default.target
"

write_unit target-intel-vault-sync.timer "[Unit]
Description=Target Intelligence — 每 10 分钟检测 Vault 审阅变更

[Timer]
OnBootSec=2min
OnUnitActiveSec=10min
Persistent=true
RandomizedDelaySec=60

[Install]
WantedBy=timers.target
"

write_unit target-intel-weekly.timer "[Unit]
Description=Target Intelligence — 每周周报（北京时间周一 07:00 = UTC 周日 23:00）

[Timer]
# 23:00 UTC 周日 = 北京时间周一 07:00
OnCalendar=Sun *-*-* 23:00:00
Persistent=true
RandomizedDelaySec=600

[Install]
WantedBy=timers.target
"

systemctl --user daemon-reload
systemctl --user enable --now target-intel-collect.timer target-intel-weekly.timer target-intel-vault-sync.timer

echo ""
echo "已安装 user systemd timer："
systemctl --user list-timers 'target-intel-*' --no-pager || true
echo ""
echo "提示：logout 后 timer 仍需运行请执行（需 sudo）："
echo "  sudo loginctl enable-linger $USER"
