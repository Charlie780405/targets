# PLAN-002: 文献质量与研判（纲领）

## 目标

在 PLAN-001 MVP 跑通采集与周报草稿基础上，解决 **Obsidian 卡片信息不足、弱相关文献过多、缺少中文提炼** 三类问题，使人工审核效率可支撑连续 4 周 MVP 验收。

## 背景

- WT-001f 遗留：日报/监管源/第二靶点/pgvector/插件/webhook → 本纲领聚焦 **文献链路**。
- 库内已有 DOI/摘要，导出层未展示；检索 `(靶点 AND 适应症)` 过宽导致 `06-Publications/` 噪音高。

## 子计划索引

| 编号 | 交付 | 依赖 |
| --- | --- | --- |
| 002a | 富导出（PMID/DOI/摘要/链接）+ `review_sync` CLI | — |
| 002b | 检索收紧 + 相关性评分 + 导出门槛 | 002a |
| 002c | LLM 文献分析（中文要点，默认 pending） | 002a |
| 002d | Dashboard 待审队列 + 周报同周期去重 | 002a,b |

## 验收（纲领级）

| # | 条件 |
| --- | --- |
| V1 | `bash scripts/verify-plan-002.sh` 全 PASS |
| V2 | Obsidian 文献卡片含 DOI + PubMed 链接 + 完整摘要 |
| V3 | 新采集弱相关事件可自动 rejected 或不出 Event |
| V4 | `--enrich-publications` 产出中文分析块（无 API 时规则降级） |
| V5 | `00-Dashboard/待审队列.md` 可按 significance 排序 |
| V6 | 同周期周报不重复堆叠 RPT 文件 |

## Out of Scope

- Obsidian 插件、pgvector、第二靶点、监管源全量
