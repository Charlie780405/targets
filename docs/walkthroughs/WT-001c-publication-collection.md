# WT-001c: PubMed 采集与去重

对应 [PLAN-001c](../plans/PLAN-001-target-intel-mvp/PLAN-001c-publication-collection.md)。合并 commit: `af900e5`（feat: `ae29c81`）。

## 执行摘要

- **目标**：接入 PubMed E-utilities + Crossref 补充，PMID/DOI 去重，摘要级抽取，撤稿标记，生成 `publication` 事件。
- **涉及文件**：18 个新增，+1014 行。
- **关键能力**：靶点/适应症检索式、XML 解析、Crossref enrich、publication 落库与事件。

## 变更明细

| 文件 | 摘要 |
| --- | --- |
| `packages/source_adapters/pubmed/` | esearch/efetch、query_builder、parser（含撤稿检测） |
| `packages/source_adapters/crossref/adapter.py` | DOI 元数据 enrich |
| `packages/entity_resolution/dedup.py` | DOI→PMID→标题去重键 |
| `apps/processor/publication_extract.py` | 规则抽取 study_type、靶点命中 |
| `apps/collector/run_pubmed.py` | 采集入口 |
| `scripts/verify-plan-001c.sh` | 专项验证 12 项 |

## 验证结果

| # | 项 | 结果 | 备注 |
| --- | --- | --- | --- |
| V1 | verify-plan-001c | 12/12 PASS | |
| V2 | pytest pubmed + dedup | 10/10 PASS | mock 回放，无真实外网 |
| V3 | PubMed+Crossref 去重合并 | PASS | DOI 优先合并 published_at |
| V4 | 撤稿样例 | PASS | `retracted=True` + 事件 summary 标记 |
| V5 | ruff + mypy | PASS | |

## 回归确认

- verify-plan-001b 测试仍通过（19 项合计）。

## 已知限制

- esearch `retmax=100`，未做全量历史回溯分页。
- Europe PMC 适配器列入 config 备注，本期未实现。

## 遗留问题与下阶段输入

- [x] SourceDocument / content_hash 范式稳定 → **001d 可复用**
- [ ] publication novelty 判定 → **001e**
- [ ] NCBI_API_KEY 生产环境配置 → **001f 部署**
