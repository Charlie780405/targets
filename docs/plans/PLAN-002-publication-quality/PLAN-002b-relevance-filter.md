# PLAN-002b: 文献相关性过滤（P0 · Vault 门外）

## 定位

**本纲领第一优先级子计划。** 目标不是「采更多」，而是 **弱相关论文不进 Obsidian Vault**。  
人工审核面只保留值得打开的过线文献；库内可保留 `Publication` 去重记录，但 **Vault 是研判界面，不是垃圾堆**。

## 目标

1. 收紧 PubMed 检索，减少源头噪音  
2. 采集阶段：低 relevance **不生成 Event**  
3. 发布阶段：未过线 Event **不写入 Vault**  
4. 发布阶段：**prune** 历史中已导出但现已过线的 `06-Publications/*.md`  
5. 人工 `review_status: rejected` 的笔记在下次 publish 时移出 Vault  

## 双门槛架构

```
PubMed esearch（Title 含靶点）
        │
        ▼
  efetch + Publication 落库（始终，供 DOI/PMID 去重）
        │
        ▼
  relevance 规则评分
        │
   ┌────┴────┐
   │ < 0.45  │──▶ 无 Event（挡在情报事件层）
   └────┬────┘
        │ ≥ 0.45
        ▼
     Event 入库
        │
        ▼
  publish 导出门（significance + relevance + review_status）
        │
   ┌────┴────────────────┐
   │ 不过线               │──▶ 跳过写入 + prune 已有 md
   └────┬────────────────┘
        │ 过线
        ▼
  06-Publications/*.md（Vault 内可见）
```

## 配置 SSOT（`config/publication_filter.yaml`）

| 键 | 默认 | 含义 |
| --- | --- | --- |
| `require_target_in_title` | `true` | 检索式靶点用 `[Title]` |
| `min_relevance_for_event` | `0.45` | 低于此分不建 Event |
| `export_min_relevance` | `0.45` | 低于此分不导出 Vault |
| `export_min_importance` | `medium` | significance 分档门槛 |
| `esearch_retmax` | `50` | 单次采集上限 |
| `prune_vault_excluded` | `true` | publish 时删除过线外 md |

## 交付物

| 路径 | 用途 |
| --- | --- |
| `config/publication_filter.yaml` | 门槛 SSOT |
| `apps/processor/publication_relevance.py` | 规则评分 + `export_min_relevance()` |
| `packages/source_adapters/pubmed/query_builder.py` | `[Title]` 子句 |
| `packages/source_adapters/pubmed/adapter.py` | retmax / require_title |
| `apps/collector/run_pubmed.py` | 采集门：低分不建 Event |
| `apps/reporter/publish.py` | 导出门 + `prune_vault_publications()` |
| `tests/test_publication_relevance.py` | 评分与检索单测 |
| `tests/test_vault_prune.py` | prune 行为单测 |

## 验证清单

| # | 步骤 | 预期 |
| --- | --- | --- |
| V1 | `bash scripts/verify-plan-002b.sh` | 全 PASS |
| V2 | `build_pubmed_query(require_target_in_title=True)` | 含 `[Title]` |
| V3 | 模拟 relevance=0.3 的 persist | 返回 `(pub, None)` |
| V4 | `publish --vault ./vault` | `skipped>0`；仅 medium+ 导出 |
| V5 | Vault 存在过线外 md 时再 publish | 文件被 prune，`pruned>0` |
| V6 | `06-Publications/` 条数 | 显著少于 Event 总数（历史噪音清退） |

## Out of Scope

- 删除 DB 内 Event（仅 Vault prune；DB 保留审计）
- LLM 相关度（留 002c；002b 纯规则）

## 遗留 / 下阶段

- 002a：过线文献补全 DOI/摘要展示  
- 002c：过线文献 LLM 中文要点  
- 可选：DB 批量 `rejected` 历史弱相关 Event（脚本，非本计划）
