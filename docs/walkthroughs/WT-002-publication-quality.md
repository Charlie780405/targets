# WT-002: 文献质量与研判

对应 [PLAN-002](../plans/PLAN-002-publication-quality/PLAN-002-publication-quality.md)。

## 执行摘要

- **002a**：Publication 富导出（PMID/DOI/摘要/链接）+ `review_sync` CLI
- **002b**：PubMed 标题检索收紧 + relevance 门槛 + publish 导过滤
- **002c**：文献分析（LLM/规则）+ `run_publication_enrich`
- **002d**：`00-Dashboard/待审队列.md` + 周报同周期去重 + `deploy-production.sh`

## 验证结果

| # | 项 | 结果 |
| --- | --- | --- |
| V1 | verify-plan-002 | 5/5 PASS |
| V2 | pytest 全量 | PASS |
| V3 | Obsidian 卡片含 DOI/摘要 | PASS（单测覆盖） |
| V4 | 生产部署 | 见下方 |

## 部署

```bash
bash scripts/deploy-production.sh
```

## 使用说明

```bash
# 文献分析 + 导出
python3 -m apps.collector.run_publication_enrich --no-llm   # 或省略 --no-llm 启用 LLM
python3 -m apps.reporter.publish --vault ./vault --enrich-publications --use-llm

# Obsidian 改 review_status 后
python3 -m apps.reporter.review_sync --vault ./vault
```

## 遗留

- [ ] 历史 100 条弱相关 Event 需人工 bulk reject 或重跑 PubMed
- [ ] Europe PMC 补充 journal 字段
- [ ] Obsidian 插件（PLAN-003）
