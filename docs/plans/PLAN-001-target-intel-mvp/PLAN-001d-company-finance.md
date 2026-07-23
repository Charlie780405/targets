# PLAN-001d: 公司与投融资采集（第4周）

## 父纲领进度

父纲领 [PLAN-001](PLAN-001-target-intel-mvp.md)。依赖 001a（实体模型）、001b（SourceDocument/Event 落库范式）。

## 上一子计划缺口分析

- 读 WT-001b/001c「遗留」：复用 SourceDocument 落库、去重、快照机制。

## 目标

接入 10–20 家目标公司 IR / 新闻稿 / RSS，加 SEC EDGAR 或交易所公告，做**公司↔药物↔靶点实体匹配**，实现来源可靠性评分（evidence_level → confidence 输入），生成 `deal`（投融资/授权/并购）与 `clinical_result`（公司披露的读出）线索事件。

## 依赖

- 001a；`config/sources/companies.yaml`（公司 IR/RSS 白名单）。

## Out of Scope

- 通用全网公司发现（只做白名单内公司）。
- 交易金额的深度结构化（LLM 抽取放 001e）。

## 关键决策

| # | 决策 | 理由 |
| --- | --- | --- |
| D1 | RSS 优先，无 RSS 才做稳定页面抓取 | 遵守采集优先级 |
| D2 | 公司→资产→靶点用种子表 + 别名匹配 | 避免旧代码/新名/合作方被当三个药 |
| D3 | 来源可靠性用 evidence_level（C 级=公司稿） | 与 confidence 口径统一 |

## 交付物 / 变更文件清单

| 路径 | 操作 | 用途 |
| --- | --- | --- |
| `packages/source_adapters/company_ir/adapter.py` | 新增 | RSS/页面抓取公司披露 |
| `packages/source_adapters/sec_edgar/adapter.py` | 新增 | SEC 公告（8-K 等） |
| `packages/entity_resolution/asset_resolver.py` | 新增 | 研发代码↔通用名↔公司↔靶点↔机制 |
| `packages/entity_resolution/org_normalizer.py` | 新增 | 公司名归一（含并购历史） |
| `apps/processor/source_reliability.py` | 新增 | 来源可靠性 → confidence 输入 |
| `config/sources/companies.yaml` | 新增 | 目标公司白名单 + RSS URL |
| `tests/cassettes/company_*.yaml`、`tests/test_asset_resolver.py` | 新增 | VCR + 实体匹配测试 |
| `scripts/verify-plan-001d.sh` | 新增 | 专项验证 |

## 验证清单

| # | 步骤 | 预期 |
| --- | --- | --- |
| V1 | `bash scripts/verify-plan-001d.sh` | 全 PASS |
| V2 | `pytest -q tests/test_asset_resolver.py` | 通过 |
| V3 | 同一资产旧代码+新通用名 | 解析为同一 Asset |
| V4 | 公司稿 → deal/clinical_result 线索事件 | 正确分类 + evidence_level=C |
| V5 | `ruff check . && mypy .` | 零错误 |

## 遗留 / 下阶段输入

- 001e 需要：跨源合并规则（同一读出出现在 CT.gov + 公司稿 + 论文时合并为一事件）。
