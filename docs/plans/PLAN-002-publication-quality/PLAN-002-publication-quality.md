# PLAN-002: 文献质量与研判（纲领）

## 目标

在 PLAN-001 MVP 跑通采集与周报草稿基础上，解决 **Obsidian 卡片信息不足、弱相关文献过多、缺少中文提炼** 三类问题，使人工审核效率可支撑连续 4 周 MVP 验收。

## 执行顺序（强制）

> **002b 优先**：弱相关论文必须挡在 Vault 门外，再谈富导出与 LLM 提炼。  
> 避免「先导出 100 条垃圾 → 再人工删」的 MVP 反模式。

| 阶段 | 子计划 | 目标 |
| --- | --- | --- |
| **P0** | **002b** | 采集 + 发布双门槛；Vault 只保留过线事件；历史噪音 prune |
| P1 | 002a | 过线文献卡片含 DOI/摘要/链接 |
| P2 | 002c | 过线文献中文研判草稿 |
| P3 | 002d | 待审 Dashboard + 周报去重 |

依赖关系调整：**002a/c/d 均依赖 002b 的 Vault 门禁**；002a 与 002c 可并行，但不得绕过 002b 导出。

## 背景

- WT-001f 遗留：日报/监管源/第二靶点/pgvector/插件/webhook → 本纲领聚焦 **文献链路**。
- 库内已有 DOI/摘要，导出层未展示；检索 `(靶点 AND 适应症)` 过宽导致 `06-Publications/` 噪音高。

## 子计划索引

| 编号 | 交付 | 依赖 |
| --- | --- | --- |
| **002b** | **Vault 门外双门槛 + prune** | —（**最先做**） |
| 002a | 富导出（PMID/DOI/摘要/链接）+ `review_sync` CLI | 002b |
| 002c | LLM 文献分析（中文要点，默认 pending） | 002b, 002a |
| 002d | Dashboard 待审队列 + 周报同周期去重 | 002b |

## 002b 核心原则（Vault 门外）

1. **采集门**：`relevance < min_relevance_for_event` → 只落 `Publication`（去重用），**不生成 Event**。
2. **导出门**：`rejected` / `significance < export_min_importance` / `relevance < export_min_relevance` → **不写 Vault**。
3. **清理门**：`publish` 时 **prune** `06-Publications/` 中已不满足门槛的历史 md（配置 `prune_vault_excluded: true`）。
4. **检索收紧**：靶点别名默认 `[Title]` 必选，禁止仅靠摘要沾边入库。

## 验收（纲领级）

| # | 条件 |
| --- | --- |
| V1 | `bash scripts/verify-plan-002.sh` 全 PASS |
| V2 | 新 PubMed 采集：弱相关 **无 Event** |
| V3 | `publish` 后 `06-Publications/` 仅含过线事件；`skipped` + `pruned` 可观测 |
| V4 | Obsidian 文献卡片含 DOI + PubMed 链接 + 完整摘要（002a） |
| V5 | `--enrich-publications` 产出中文分析块（002c） |
| V6 | 同周期周报不重复堆叠 RPT 文件（002d） |

## Out of Scope

- Obsidian 插件、pgvector、第二靶点、监管源全量
