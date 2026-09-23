# WT-002：WeKnora 文献证据接收端

状态：代码和隔离数据库门禁完成；Targets `main` 已合并推送 `7a50cb2`；真实公网 API Key/KB 拉取联调待配置专用 retrieve Key 后执行。

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

真实联调命令（不把 Key 写入命令行或仓库）：

```bash
export WEKNORA_BASE_URL=https://weknora.qyunsgen.com
export WEKNORA_TARGETS_API_KEY='由密钥管理注入'
python3 -m apps.collector.run_weknora_literature \
  --knowledge-base-id '<KB_ID>'
```

## 回滚与遗留

关闭定时/手工同步即可；数据库回滚使用 `alembic downgrade 62cca6f53ae0`，不删除既有 WeKnora 事件审计。真实联调仍需验证 retrieve Key 的 KB allow-list、重复拉取、撤销同步、失效 Key 和生产备份恢复。
