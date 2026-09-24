# WT-002：WeKnora 文献证据接收端

状态：代码、隔离数据库门禁、真实公网正向/幂等/撤销同步、人工审核回写、Targets 浏览器工作台和单 KB 短窗口调度验收完成；Targets 接收实现和重复标识修复已合并到 `main`；常驻调度默认关闭，正式备份恢复与全量生产启用仍待独立门禁。

## 目标

将 WeKnora 的 `weknora.targets.approved-evidence` v1 集合安全拉取到 Targets 本地数据库的待审投影。同步不下载原件、不写任意 URL、不自动发布 Vault、不生成医学结论。

## 实现

- `apps/collector/weknora_literature.py`：Pydantic 外部响应校验、分页一致性、状态/权利门禁、重定向拒绝、内部存储字段拒绝和 API Key 请求头边界。
- `apps/collector/run_weknora_literature.py`：受环境变量或 owner-only 文件提供 Key 的同步 CLI，默认写本地待审投影，`--dry-run` 只拉取不落库。
- `apps/collector/scheduler.py`：在 scheduler profile 中按 UTC 每日注册可选 WeKnora 同步；默认关闭，配置不完整、密钥文件不是 owner-only 或时间无效时不注册，命令行不携带密钥内容。
- `WeKnoraEvidenceProjection`：以 `knowledge_base_id + artifact_id` 唯一幂等；内容哈希改变或 revoked 投影重新出现时重新进入 pending；完整集合中消失的记录标记 `revoked`，不删除事件、来源或证据审计。
- 有 DOI/PMID/PMCID 时生成 canonical 来源链接；无法从交换包判定来源等级时保守落为 E 级并保留 `weknora://` 内部追踪 URI，不把待审投影伪装成医学结论。
- 现有 Vault 发布和 frontmatter 回写均拒绝 revoked 投影；其它 Targets 事件保持原有行为。
- `apps/review_workbench.py` 与 `apps/review_workbench_ui.py`：默认关闭的回环浏览器工作台，按限定 KB 分页展示脱敏投影；审核写回必须携带秘密令牌，并拒绝 revoked/孤儿投影。
- 工作台只展示白名单中的题录、来源、页级摘录和哈希，不展示 `source_url`、`download_url`、`storage_key`、`host_path` 或原件；前端使用 DOM `textContent`，不把外部证据当 HTML。
- `migrations/versions/002_weknora_evidence_projection.py`：增加可回退投影表。

## 验证

```bash
bash scripts/verify-plan-002-weknora-consumer.sh
```

已通过：7 项 Python 契约/幂等/来源等级/撤销重现测试、ruff 检查、Alembic upgrade → downgrade → upgrade。全仓 `mypy` 仍有两个既有错误（`apps/processor/llm_extract.py` 的 unused ignore、`publication_analysis.py` 的 redundant cast），与本切片无关；全仓 pytest 另有既有的 `tests/test_vault_prune.py` 必填参数失败，与本切片无关。

### 2026-09-24 真实公网联调

- 使用仅授予 `retrieve`、且只允许 KB `203262b3-452d-4066-9f7f-6c97eba87ffc` 的短期 Key；Key 仅保存于 Targets `secrets/` 下的 owner-only 文件，不写入 Git、日志或命令参数，明文不进入本记录。
- 目标 SQLite 先从 Alembic `62cca6f53ae0` 升级到 `9b8f2c1d7e4a`，升级前保留权限为 `0600` 的备份，迁移后确认投影表存在且当前为 head。
- 真实 dry-run 返回 `fetched=5`；首次写入暴露 JLSS/Mayiso 同一 PMID/DOI 在批内重复创建 Publication 的缺陷。修复为每条工件处理前显式 flush，使共享标识复用 canonical Publication；针对该场景新增回归测试。
- 修复后真实写入返回 `fetched=5 created=5`，第二次真实复跑返回 `fetched=5 unchanged=5`；数据库核对为 `projections=5 active=5`，所有投影保持待审，不触发 Vault 发布。
- 使用无效 Key 的真实 dry-run 返回 HTTP 401，且没有写库；此前的重复失败事务也已回滚，没有半成品投影。

### 2026-09-24 撤销传播与人工审核回写门禁

- 使用 Targets 当前 SQLite 的临时备份副本，预置与 WeKnora 已撤销工件对应的 active 投影；随后通过真实公网集合和真实限定 Key 执行正式同步 CLI，返回 `fetched=5 updated=5 revoked=1`。副本中的投影最终为 `status=revoked` 且 `revoked_at` 非空；主 Targets 数据库仍保持 `active=5`，未修改生产投影。
- 在另一份临时副本中通过正式 `sync_collection` 生成 pending 事件和 Vault 审核笔记，模拟审核者只修改 `review_status: pending` 为 `approved`，再运行正式 `review_sync`；结果为 `review_notes=1 review_updated=1 status=approved publish_gate=True`。这证明人工审核回写和 WeKnora 投影活动状态发布门禁连通，临时副本随后删除。
- 两次门禁均不下载原件、不写 WeKnora、不推送 Vault、不改变主 Targets 数据；临时副本、临时 Vault 和测试对象均已清理。

### 2026-09-24 定时调度配置门禁

- 新增 `WEKNORA_SYNC_ENABLED`、`WEKNORA_BASE_URL`、`WEKNORA_TARGETS_KB_ID`、密钥来源及 UTC 时刻配置；默认关闭，不会因升级自动启动 WeKnora 拉取。
- owner-only 文件和环境变量两种密钥来源均只在同步子进程中读取；调度器命令只传文件路径或环境变量名，日志不记录 Key。
- 配置缺失、密钥文件不存在/权限超过 `0600`、地址含用户信息或查询参数、时间越界时，调度器安全跳过并保留其它采集作业。
- `tests/test_scheduler.py` 4 项、工作台专项 7 项、全仓 `pytest` 和 ruff 均通过；单 KB 短窗口调度另有 PLAN-002 O3 证据，常驻 scheduler profile 仍默认关闭。

### 2026-09-24 Targets 浏览器工作台

- 访问 `/targets/review` 前必须同时配置 `TARGETS_REVIEW_UI_ENABLED=true` 和限定 `TARGETS_REVIEW_UI_KB_ID`；默认关闭时返回 404。建议只通过回环绑定/SSH 隧道访问，不将 health 端口公开到公网。
- `GET /targets/api/projections?status=pending|active|revoked|all&limit=...&offset=...` 返回统一分页结构；`PATCH /targets/api/projections/{projection_id}/review` 需要 `Authorization: Bearer <TARGETS_REVIEW_UI_TOKEN>`，状态仅写回本地关联事件，不下载原件或自动发布医学结论。
- 审核理由仅用于请求校验和长度审计，不写入 WeKnora 投影；现有 Vault 发布门禁仍是最终发布控制点。撤销投影始终只读。

真实联调命令（不把 Key 写入命令行或仓库）：

```bash
export WEKNORA_BASE_URL=https://weknora.qyunsgen.com
export WEKNORA_TARGETS_API_KEY='由密钥管理注入'
python3 -m apps.collector.run_weknora_literature \
  --knowledge-base-id '<KB_ID>'
```

## 回滚与遗留

关闭 `WEKNORA_SYNC_ENABLED` 或 scheduler profile 即可；数据库回滚使用 `alembic downgrade 62cca6f53ae0`，不删除既有 WeKnora 事件审计。当前仍需浏览器/Targets 消费端验收、正式生产备份恢复和定时任务灰度；本次未启用 Targets 定时任务。
