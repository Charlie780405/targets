# PLAN-001c: 论文采集（第3周）

## 父纲领进度

父纲领 [PLAN-001](PLAN-001-target-intel-mvp.md)。依赖 001a。可与 001b 并行，但共用 SourceDocument/Event 落库。

## 上一子计划缺口分析

- 读 WT-001b「遗留」：确认 SourceDocument 落库与 `content_hash` 去重接口稳定，本期复用。

## 目标

接入 PubMed E-utilities，按检索式采集论文，PMID/DOI 去重，做摘要级结构化抽取（靶点/药物/适应症/研究类型），处理勘误与撤稿标记，生成 `publication` 事件。补充源 Crossref/Europe PMC 提供 DOI 与在线发表时间。

## 依赖

- 001a；`config/sources/pubmed.yaml`；建议配 `NCBI_API_KEY`。

## Out of Scope

- 付费墙全文；PMC 仅取许可允许的全文（本期可只做摘要级）。
- 全文语义抽取（留后期）。

## 关键决策

| # | 决策 | 理由 |
| --- | --- | --- |
| D1 | esearch→efetch 分步，存原始 XML/JSON | 可追溯 |
| D2 | 去重键 = DOI 优先，退化用 PMID + 标题归一 | 跨源合并稳定 |
| D3 | 撤稿/勘误单独标记字段，不删原事件 | 医学审计需要 |

## 交付物 / 变更文件清单

| 路径 | 操作 | 用途 |
| --- | --- | --- |
| `packages/source_adapters/pubmed/adapter.py` | 新增 | E-utilities esearch/efetch |
| `packages/source_adapters/pubmed/query_builder.py` | 新增 | 按靶点别名/适应症构建检索式 |
| `packages/source_adapters/crossref/adapter.py` | 新增 | DOI/在线发表时间补充 |
| `packages/entity_resolution/dedup.py` | 新增/扩展 | DOI/PMID/标题去重 |
| `apps/processor/publication_extract.py` | 新增 | 摘要级结构化抽取（规则+可选 LLM 占位） |
| `tests/cassettes/pubmed_*.yaml`、`tests/test_pubmed_adapter.py`、`tests/test_dedup.py` | 新增 | VCR + 去重测试 |
| `scripts/verify-plan-001c.sh` | 新增 | 专项验证 |

## 验证清单

| # | 步骤 | 预期 |
| --- | --- | --- |
| V1 | `bash scripts/verify-plan-001c.sh` | 全 PASS |
| V2 | `pytest -q tests/test_pubmed_adapter.py tests/test_dedup.py` | 通过 |
| V3 | 同一论文多源（PubMed+Crossref） | 去重为一条，DOI 合并 |
| V4 | 撤稿标记样例 | 事件带 retracted 标记 |
| V5 | `ruff check . && mypy .` | 零错误 |

## 遗留 / 下阶段输入

- 001e 需要：publication 事件 novelty 判定（是否已在既往周报出现）。
