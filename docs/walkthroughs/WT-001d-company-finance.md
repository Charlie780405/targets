# WT-001d: 公司与投融资采集

对应 [PLAN-001d](../plans/PLAN-001-target-intel-mvp/PLAN-001d-company-finance.md)。合并 commit: `df34f71`（feat: `54b0410`）。

## 执行摘要

- **目标**：公司 IR/RSS + SEC EDGAR，实体匹配，来源可靠性评分，生成 deal / clinical_result 线索事件。
- **涉及文件**：18 个新增，+911 行。
- **关键能力**：RSS 采集、8-K submissions、asset/org 归一、规则分类、confidence=C 级映射。

## 变更明细

| 文件 | 摘要 |
| --- | --- |
| `packages/source_adapters/company_ir/` | RSS 解析、原始 JSON 落盘 |
| `packages/source_adapters/sec_edgar/` | SEC submissions API，8-K/6-K |
| `packages/entity_resolution/{asset_resolver,org_normalizer}.py` | 药物/公司实体匹配 |
| `apps/processor/{source_reliability,company_event_classifier}.py` | C 级 confidence、deal/读出分类 |
| `apps/collector/run_companies.py` | 采集入口 |
| `scripts/verify-plan-001d.sh` | 专项验证 13 项 |

## 验证结果

| # | 项 | 结果 | 备注 |
| --- | --- | --- | --- |
| V1 | verify-plan-001d | 13/13 PASS | |
| V2 | pytest asset_resolver | PASS | REGN668↔dupilumab 同一资产 |
| V3 | 旧代码+新通用名 | PASS | |
| V4 | deal / clinical_result 分类 | PASS | evidence_level=C |
| V5 | ruff + mypy | PASS | |

## 已知限制

- 多数公司 `rss_url` 仍待补全（仅 Regeneron 已配置）。
- SEC 仅覆盖配置了 `sec_cik` 的美股公司。

## 遗留问题与下阶段输入

- [ ] 跨源合并（CT.gov + 公司稿 + 论文）→ **001e**
- [ ] trial_change significance 初判（Results Posted→高）→ **001e**
- [ ] publication novelty 判定 → **001e**
