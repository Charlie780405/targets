# PLAN-001b: 临床试验采集（第2周）

## 父纲领进度

父纲领 [PLAN-001](PLAN-001-target-intel-mvp.md)。依赖 001a（领域模型、Trial 字段、靶点词典）。

## 上一子计划缺口分析

- 读 WT-001a「遗留」：确认 Trial 字段清单与 `content_hash` 规则已定稿；若未定，本期先补齐。

## 目标

接入 ClinicalTrials.gov API v2，按首发靶点/适应症增量采集试验，保存原始 JSON 快照，建 Trial 表，实现**版本快照与字段差异检测**，把有医学意义的字段变化翻译成 `trial_change` 事件。

## 依赖

- 001a 完成；`config/sources/clinicaltrials.yaml` 就绪。

## Out of Scope

- 结果数值的深度解析（留给 001e LLM 抽取）。
- 论文/公司源。

## 关键决策

| # | 决策 | 理由 |
| --- | --- | --- |
| D1 | 用 API v2 + OpenAPI 分页增量 | 官方结构化，稳定 |
| D2 | 每次抓取存整份 JSON 快照到 `data/raw/clinicaltrials/` | 可回溯、可重放 diff |
| D3 | diff 只针对监测字段清单 | 避免噪声更新变事件 |

## 监测字段（diff → trial_change）

`Overall Status`、`Enrollment`、`Primary Completion Date`、`Study Completion Date`、`Outcome Measures`、`Results Posted`、`Sponsor`、`Locations`。

## 交付物 / 变更文件清单

| 路径 | 操作 | 用途 |
| --- | --- | --- |
| `packages/source_adapters/clinicaltrials/adapter.py` | 新增 | fetch() 增量拉取 + 存快照 |
| `packages/source_adapters/clinicaltrials/parser.py` | 新增 | JSON→Trial 字段映射 |
| `apps/processor/trial_diff.py` | 新增 | 两版本快照字段 diff → trial_change 事件 |
| `apps/collector/run_clinicaltrials.py` | 新增 | 采集入口（供定时调用） |
| `tests/cassettes/clinicaltrials_*.yaml` | 新增 | VCR 录制真实响应 |
| `tests/test_clinicaltrials_adapter.py`、`tests/test_trial_diff.py` | 新增 | 采集 + diff 测试 |
| `scripts/verify-plan-001b.sh` | 新增 | 专项验证 |

## 验证清单

| # | 步骤 | 预期 |
| --- | --- | --- |
| V1 | `bash scripts/verify-plan-001b.sh` | 全 PASS |
| V2 | `pytest -q tests/test_clinicaltrials_adapter.py`（VCR 回放） | 通过，无真实外网 |
| V3 | 两份快照跑 diff | 正确产出 trial_change 事件；无意义更新不产出 |
| V4 | 采集入口对首发靶点跑一次 | 落原始 JSON + Trial 记录 |
| V5 | `ruff check . && mypy .` | 零错误 |

## 遗留 / 下阶段输入

- 001e 需要：trial_change 事件的 significance 初判规则输入（如 Results Posted→高）。
