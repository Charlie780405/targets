# PLAN-003: 文献审核队列与研判摘要

## 目标

MVP 已跑通采集与 Vault 同步，但 **审核面只有 1 篇弱相关文献**、**无 LLM 中文摘要效果**、**审核后无汇总**。本计划补齐「该审谁 → 怎么审 → 审完怎么总结」闭环。

## 上一阶段缺口（PLAN-002 / WT-002）

| 缺口 | 根因 | 归并 |
| --- | --- | --- |
| Vault 只剩 1 篇且相关性低 | 导出只看 significance≥medium，多数 Event 未评分；AIT 综述碰巧 0.55 | 003a |
| 待审 Dashboard 列 8 条但 Vault 1 条 | Dashboard 读全库 pending，与 Vault 导出门不一致 | 003b |
| 研判草稿为规则降级 | publish 未默认 `--use-llm --enrich-publications` | 003c |
| 审核后总结不可见 | 无 `approved` 文献_digest 产物 | 003d |

## 子计划

| 编号 | 交付 |
| --- | --- |
| 003a | `relevance_profile.yaml` 管线优先词 + 惩罚词；提高有效 relevance |
| 003b | **审核队列 Top-N**（按 relevance 导出待审文献，默认 10 篇）+ publish 前全量评分 |
| 003c | enrich 默认对队列内文献生成中文摘要；Vault 展示研判块 |
| 003d | `00-Dashboard/已审核文献摘要.md` + 周报 §approved 文献汇总 |

## 验收

- Vault `06-Publications/` 含 **Top-N 高 relevance** 待审文献（含 Dupilumab/III 期类）
- 每篇含 **中文研判草稿**（LLM 或规则）
- `approved` 后 publish 生成 **已审核文献摘要**
- Dashboard 表格列不错位，与 Vault 队列一致
