# PLAN-001f: Obsidian 与运行保障（第6周）

## 父纲领进度

父纲领 [PLAN-001](PLAN-001-target-intel-mvp.md)。依赖 001e（周报产出）。完成即达 M6 并进入 MVP 4 周验收期。

## 上一子计划缺口分析

- 读 WT-001e「遗留」：周报导出格式、frontmatter 对齐、审核回写路径；本期实现导出器与同步。

## 目标

建立 Obsidian Vault 模板与 Markdown 发布器，把事件/周报导出为带 frontmatter 的笔记；用私有 Git 仓库做云端→本地同步；配置定时采集任务与错误告警；建立采集覆盖率、重复率、人工接受率评估。让系统在混合架构下持续运行。

## 依赖

- 001e；私有 Vault Git 仓库；Vultr 主机；`VAULT_GIT_REMOTE`。

## Out of Scope

- Obsidian 插件开发（用文件级导出即可；插件放后期，且须独立测试 Vault）。
- 日报调度。

## 关键决策

| # | 决策 | 理由 |
| --- | --- | --- |
| D1 | 云端只产 Markdown → push 私有仓库 → 本地拉取 | 第一版同步极简，敏感数据不进普通云同步 |
| D2 | 定时用 systemd timer（或 APScheduler 常驻） | 不让交互式会话成为生产唯一依赖 |
| D3 | 审核状态在 Obsidian 改，回写 DB 为 SSOT | Obsidian 是研判界面 |

## 交付物 / 变更文件清单

| 路径 | 操作 | 用途 |
| --- | --- | --- |
| `packages/obsidian_exporter/exporter.py` | 新增 | Event/Report → frontmatter Markdown，写 Vault 目录 |
| `packages/obsidian_exporter/vault_layout.py` | 新增 | 00-Dashboard…99-Templates 目录规范 |
| `apps/reporter/publish.py` | 新增 | 导出 + Git commit/push Vault |
| `apps/reporter/review_sync.py` | 新增 | 从 Vault frontmatter 回写 review_status 到 DB |
| `scripts/schedule/*.timer`、`*.service` | 新增 | systemd 定时采集/报告 |
| `apps/*/health.py`（FastAPI `/health`） | 新增 | 版本与运行状态 |
| `apps/processor/metrics.py` | 新增 | 覆盖率/重复率/接受率评估 |
| `docker-compose.yml` | 新增 | Vultr 部署 |
| `scripts/verify-plan-001f.sh` | 新增 | 专项验证 |

## 验证清单

| # | 步骤 | 预期 |
| --- | --- | --- |
| V1 | `bash scripts/verify-plan-001f.sh` | 全 PASS |
| V2 | 导出一份周报到 Vault | frontmatter 合规、目录正确 |
| V3 | Git 同步 | 云端 push → 本地 pull 成功 |
| V4 | 在 Vault 改 review_status → 回写 | DB 状态更新 |
| V5 | 定时任务触发一次采集 | 日志正常、告警通道可用 |
| V6 | `curl /health` | 版本 = git HEAD |
| V7 | 覆盖率/重复率/接受率报表 | 指标可计算 |

## MVP 验收（运行期）

连续 4 周产出周报；每周记录：漏报抽检、重复率、人工接受率、是否省时。达标即 MVP 完成，进入扩展（日报、大会、监管、多靶点、pgvector）。

## 遗留 / 下阶段输入（PLAN-002 扩展）

- 日报、更多大会适配器、监管源、第二靶点、pgvector 语义关联、网站/浏览器扩展接入医学研发工作台。
