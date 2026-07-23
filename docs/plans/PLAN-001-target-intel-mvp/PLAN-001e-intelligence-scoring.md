# PLAN-001e: 情报生成（第5周）

## 父纲领进度

父纲领 [PLAN-001](PLAN-001-target-intel-mvp.md)。依赖 001b/001c/001d 全部落库能力。

## 上一子计划缺口分析

- 汇总 WT-001b/001c/001d「下阶段输入」：significance 初判规则、novelty 判定、跨源合并规则；本期统一实现。

## 目标

把已落库的多源事件做**分类 → 三分数评分 → 跨来源合并 → LLM 结构化抽取 → 周报生成**，产出端到端第一份含证据链的中文周报（待人工审核）。这是 M5 里程碑。

## 依赖

- 001b/001c/001d；`OPENAI_API_KEY`（或等价 LLM）。

## Out of Scope

- 无人工审核直接发布（发布门槛见 medical-review-rules）。
- 日报（接口预留，不实现）。
- 训练自有评分模型（先规则）。

## 关键决策

| # | 决策 | 理由 |
| --- | --- | --- |
| D1 | 规则评分，权重 25/30/20/15/10 | 可解释、可回溯；后期再模型 |
| D2 | 三分数分列（significance/confidence/novelty） | 避免「重要但未证实」与「可靠但无关」混淆 |
| D3 | LLM 只做结构化抽取/摘要，输出 Schema 校验 | 不产生无证据结论 |
| D4 | 跨源合并键 = 靶点+资产+适应症+event_date 窗口 | 同一读出合并为一事件多证据 |

## 评分公式

```
total = 来源可靠性×0.25 + 医学重要性×0.30 + 新颖性×0.20 + 靶点相关性×0.15 + 时间敏感性×0.10
```

## 交付物 / 变更文件清单

| 路径 | 操作 | 用途 |
| --- | --- | --- |
| `apps/processor/classify.py` | 新增 | 事件类型分类 |
| `apps/processor/scoring.py` | 新增 | 三分数评分（读 config 权重） |
| `apps/processor/merge.py` | 新增 | 跨来源合并（多 Evidence 挂一 Event） |
| `apps/processor/llm_extract.py` | 新增 | LLM 结构化抽取，Pydantic 校验输出 |
| `prompts/event_extract.md`、`prompts/weekly_summary.md` | 新增 | 版本化提示词 |
| `apps/reporter/weekly.py` | 新增 | 组装数据 → 渲染 weekly-brief 模板 |
| `config/scoring.yaml` | 新增 | 评分权重 + significance 规则 SSOT |
| `tests/test_scoring.py`、`tests/test_merge.py` | 新增 | 评分/合并测试 |
| `scripts/verify-plan-001e.sh` | 新增 | 专项验证 |

## 验证清单

| # | 步骤 | 预期 |
| --- | --- | --- |
| V1 | `bash scripts/verify-plan-001e.sh` | 全 PASS |
| V2 | `pytest -q tests/test_scoring.py tests/test_merge.py` | 通过 |
| V3 | 同一读出多源 | 合并为一事件、多证据 |
| V4 | III 期读出样例 | significance=high |
| V5 | 端到端跑一周窗口 | 产出含证据链的中文周报草稿 |
| V6 | LLM 输出不合 Schema | 被拒绝并降级为规则抽取 |
| V7 | `ruff check . && mypy .` | 零错误 |

## 遗留 / 下阶段输入

- 001f 需要：周报 Markdown 导出格式与 Obsidian frontmatter 对齐、审核状态回写路径。
