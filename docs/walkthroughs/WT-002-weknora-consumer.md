# WT-002：WeKnora 文献证据接收端

状态：代码、隔离数据库门禁、真实公网正向/幂等/撤销同步和人工审核回写验收完成；Targets 接收实现和重复标识修复已合并到 `main`；正式备份恢复与定时任务启用仍待独立门禁。

## 目标

将 WeKnora 的 `weknora.targets.approved-evidence` v1 集合安全拉取到 Targets 本地数据库的待审投影。同步不下载原件、不写任意 URL、不自动发布 Vault、不生成医学结论。

## 实现

- `apps/collector/weknora_literature.py`：Pydantic 外部响应校验、分页一致性、状态/权利门禁、重定向拒绝、内部存储字段拒绝和 API Key 请求头边界。
- `apps/collector/run_weknora_literature.py`：受环境变量或 owner-only 文件提供 Key 的同步 CLI，默认写本地待审投影，`--dry-run` 只拉取不落库。
- `WeKnoraEvidenceProjection`：以 `knowledge_base_id + artifact_id` 唯一幂等；内容哈希改变或 revoked 投影重新出现时重新进入 pending；完整集合中消失的记录标记 `revoked`，不删除事件、来源或证据审计。
- 有 DOI/PMID/PMCID 时生成 canonical 来源链接；无法从交换包判定来源等级时保守落为 E 级并保留 `weknora://` 内部追踪 URI，不把待审投影伪装成医学结论。
- 现有 Vault 发布和 frontmatter 回写均拒绝 revoked 投影；其它 Targets 事件保持原有行为。
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

真实联调命令（不把 Key 写入命令行或仓库）：

```bash
export WEKNORA_BASE_URL=https://weknora.qyunsgen.com
export WEKNORA_TARGETS_API_KEY='由密钥管理注入'
python3 -m apps.collector.run_weknora_literature \
  --knowledge-base-id '<KB_ID>'
```

## 回滚与遗留

关闭定时/手工同步即可；数据库回滚使用 `alembic downgrade 62cca6f53ae0`，不删除既有 WeKnora 事件审计。当前仍需浏览器/Targets 消费端验收、正式生产备份恢复和定时任务灰度；本次未启用 Targets 定时任务。
