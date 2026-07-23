# WT-001b: ClinicalTrials.gov 采集与 Trial 版本 diff

对应 [PLAN-001b](../plans/PLAN-001-target-intel-mvp/PLAN-001b-trial-collection.md)。合并 commit: `e8ba45d`（feat: `f564292`）。

## 执行摘要

- **目标**：接入 ClinicalTrials.gov API v2，增量采集试验、保存原始 JSON 快照、版本 diff 生成 `trial_change` 事件。
- **涉及文件**：17 个新增，+909 行。
- **关键能力**：IL-4Rα 检索式、8 字段 watch diff、enrollment 噪声过滤、collector 落库。

## 变更明细

| 文件 | 摘要 |
| --- | --- |
| `packages/source_adapters/clinicaltrials/{adapter,parser}.py` | API v2 分页、JSON 解析、watch 字段提取 |
| `apps/processor/trial_diff.py` | 快照 diff → trial_change Event；\|Δenrollment\|≤5 过滤 |
| `apps/collector/run_clinicaltrials.py` | 采集入口：Trial / Snapshot / SourceDocument / Event |
| `tests/cassettes/clinicaltrials_fetch.yaml` | VCR 回放（无真实外网） |
| `scripts/verify-plan-001b.sh` | 专项验证 10 项 |

## 验证结果

| # | 项 | 结果 | 备注 |
| --- | --- | --- | --- |
| V1 | verify-plan-001b | 10/10 PASS | |
| V2 | pytest（VCR） | 9/9 PASS | |
| V3 | 两份快照 diff | PASS | status 变化成事件；enrollment +3 不成事件 |
| V4 | ResultsPosted 变化 | PASS | 成事件 |
| V5 | ruff + mypy | PASS | |

## 部署记录

未部署 Vultr（本地/CI 验证阶段）。

## 回归确认

- verify-plan-001a 仍适用；001b 为增量模块，未破坏领域模型。

## 已知限制

- MVP 采集为**全量分页**，尚未按 `LastUpdatePostDate` 增量（001f 运行保障可补）。
- `target_id` / `asset_id` 尚未在采集时自动关联（001d 实体匹配后补全）。

## 遗留问题与下阶段输入

- [x] SourceDocument 落库与 content_hash 去重接口稳定 → **001c 可复用**
- [ ] trial_change significance 初判（Results Posted→高）→ **001e**
- [ ] 采集 `--since` 增量参数 → **001f**
