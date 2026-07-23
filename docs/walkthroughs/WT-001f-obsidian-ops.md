# WT-001f: Obsidian 与运行保障

对应 [PLAN-001f](../plans/PLAN-001-target-intel-mvp/PLAN-001f-obsidian-ops.md)。合并 commit: `1ca8285`（feat: `7e1f504`）。

## 执行摘要

- **目标**：事件/周报导出 Obsidian Vault（frontmatter 对齐 DB）、Git 同步、审核回写、指标评估、健康检查与 systemd/docker 调度（M6 里程碑）。
- **关键能力**：`07-Events/*` / `09-Weekly-Briefs/` 目录规范、`review_status` Vault↔DB 双向、`/health` 返回 git HEAD、覆盖率/接受率报表。

## 变更明细

| 文件 | 摘要 |
| --- | --- |
| `packages/obsidian_exporter/` | Event/Report frontmatter 导出、Vault 目录 SSOT |
| `apps/reporter/publish.py` | 导出 + git commit/push（`VAULT_GIT_REMOTE`） |
| `apps/reporter/review_sync.py` | 扫描 Vault frontmatter 回写 `medical_review_status` |
| `apps/processor/metrics.py` | 覆盖率 / 多源重复率 / 人工接受率 |
| `apps/health.py` | FastAPI `/health`（version=git HEAD、database 状态） |
| `apps/collector/scheduler.py` | APScheduler 可选常驻调度 |
| `scripts/schedule/*.service` + `*.timer` | systemd 每日采集 / 每周周报 |
| `docker-compose.yml` | health:8080 + scheduler profile |
| `scripts/verify-plan-001f.sh` | 专项验证 20 项 |

## 验证结果

| # | 项 | 结果 | 备注 |
| --- | --- | --- | --- |
| V1 | verify-plan-001f | 20/20 PASS | |
| V2 | 事件导出 frontmatter | PASS | `event_id` / `importance` / `review_status` / `sources` |
| V3 | 周报导出目录 | PASS | `09-Weekly-Briefs/{period}_{report_id}.md` |
| V4 | review_status 回写 | PASS | Vault `approved` → DB 更新 |
| V5 | systemd unit 文件 | PASS | collect.timer + weekly.timer 存在 |
| V6 | health_payload | PASS | `database=up`，`version`=git HEAD |
| V7 | metrics 报表 | PASS | 覆盖率 / 接受率可计算 |
| V8 | verify-plan-001e 回归 | 14/14 PASS | |

## 部署说明

```bash
# Vault 导出（默认 ./vault）
python3 -m apps.reporter.publish --vault ./vault

# 健康检查（需 .[server]）
uvicorn apps.health:create_app --factory --port 8080

# systemd（Vultr 主机）
sudo cp scripts/schedule/target-intel-*.{service,timer} /etc/systemd/system/
sudo systemctl enable --now target-intel-collect.timer target-intel-weekly.timer
```

环境变量：`VAULT_PATH`、`VAULT_GIT_REMOTE`、`DATABASE_URL`。

## 已知限制

- Git push 需配置私有 Vault 仓库与 SSH/credential；无 remote 时仅本地 commit。
- 告警通道（邮件/Slack）未实现，仅 journal/docker logs。
- MVP 验收期（连续 4 周周报）需在运行期人工记录。

## 遗留问题与下阶段输入（PLAN-002）

- [ ] 日报调度与更多数据源（监管、大会全量）
- [ ] 第二靶点、pgvector 语义关联
- [ ] Obsidian 插件（独立测试 Vault）
- [ ] 告警 webhook 集成
