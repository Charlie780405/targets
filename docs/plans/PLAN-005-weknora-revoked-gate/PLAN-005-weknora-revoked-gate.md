# PLAN-005：WeKnora 来源失效后的发布门禁

对应 WeKnora PLAN-005g-3 的第一块（撤销/失效阻止发布）。状态：已实现，未部署。

## 问题

`sync_collection` 在 WeKnora 不再列出某工件（撤销、权利到期、取消发布、被取代）时把投影置 `revoked`，审核工作台与 Vault 导出据此拒绝。但周报（`weekly`）、已审文献摘要（`approved_digest`）和审核队列（`review_queue`）只看 `medical_review_status`：一个曾被批准、随后来源被撤销的事件仍会作为“已批准结论”出现在周报与摘要里。

## 变更

- `apps/weknora_history.weknora_available_clause()`：SQL 条件，排除绑定了非 active 历史投影的事件；未绑定投影的旧事件不受影响。新采集已在 PLAN-006 退役。
- 应用到 `weekly._query_events`、周报已批准文献、`approved_digest`、`review_queue` 的已批准与待审查询（Vault 导出原本已用 `is_active_weknora_event`）。
- 事件与审核记录保留，不改写人工结论；来源恢复后沿用既有行为——事件重置为待审，不自动恢复批准。

## 验证

`tests/test_weknora_revoked_gate.py`：批准后 → 四个出口可见；来源撤销 → 四个出口全部不可见且事件/批准记录保留；来源恢复 → 回到待审、不再出现在已审摘要；无投影的旧事件不受影响。去掉修复后第一个用例失败（已核对）。`bash scripts/verify-plan-005.sh`。

## 未做（WeKnora 005g-3 余下）

- 消费 WeKnora 结果 feed（`weknora.literature.results` v1）的 revision：原件 SHA 不变但结果变更时更新并重审受影响事件（目前仍读 v1 `targets-evidence`，没有结果 revision）。
- 来源类型 → EvidenceLevel 的配置化映射（现为代码内保守映射：PubMed/PMC → B，其余 → E，从不给 A）。
- 周报/摘要里对“因来源失效而撤下”的事件的显式提示。
