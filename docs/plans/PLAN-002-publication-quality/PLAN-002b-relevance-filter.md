# PLAN-002b: 文献相关性过滤

## 目标

收紧 PubMed 检索（标题含靶点）；入库前 relevance 评分；低于阈值不生成 Event；publish 跳过 rejected 与低 significance。

## 交付物

| 路径 | 用途 |
| --- | --- |
| `config/publication_filter.yaml` | SSOT 门槛 |
| `apps/processor/publication_relevance.py` | 规则评分 |
| `packages/source_adapters/pubmed/query_builder.py` | `[Title]` 子句 |
| `apps/collector/run_pubmed.py` | 入库门槛 |
| `apps/reporter/publish.py` | `--min-importance` |

## 验证

`bash scripts/verify-plan-002b.sh`
