# PLAN-002d: 审核 Dashboard 与周报去重

## 目标

生成 `00-Dashboard/待审队列.md` 与指标摘要；同周期周报更新而非重复新建。

## 交付物

| 路径 | 用途 |
| --- | --- |
| `apps/reporter/dashboard.py` | Vault Dashboard 导出 |
| `apps/reporter/weekly.py` | save_weekly_report 去重 |
| `scripts/deploy-production.sh` | Vultr 生产部署 |

## 验证

`bash scripts/verify-plan-002d.sh`
