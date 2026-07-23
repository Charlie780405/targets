# WT-001e: 情报生成与周报

对应 [PLAN-001e](../plans/PLAN-001-target-intel-mvp/PLAN-001e-intelligence-scoring.md)。合并 commit: `5a5bf98`（feat: `87ba85b`）。

## 执行摘要

- **目标**：对已落库多源事件做分类 → 三分数评分 → 跨源合并 → LLM/规则抽取 → 中文周报草稿（M5 里程碑）。
- **关键能力**：`config/scoring.yaml` SSOT、significance/confidence/novelty 分列、7 日窗口合并、Pydantic 校验 + 规则降级、`generate_weekly_brief` 端到端。
- **附带修复**：公司 IR / SEC 适配器网络超时容错（`httpx.HTTPError` 跳过并 WARN，不拖垮整次采集）。

## 变更明细

| 文件 | 摘要 |
| --- | --- |
| `config/scoring.yaml` | 权重 25/30/20/15/10、significance 规则、合并窗口、novelty 惩罚 |
| `apps/processor/classify.py` | 事件类型/阶段归一（规则 + 复用 company_classifier） |
| `apps/processor/scoring.py` | 三分数计算、标签阈值（高/中/低） |
| `apps/processor/merge.py` | 靶点+资产+适应症+类型 + 7 日窗口合并，多 Evidence 挂组 |
| `apps/processor/llm_extract.py` | LLM 结构化抽取，Schema 不合规降级 `rule_based_extract` |
| `prompts/event_extract.md`、`prompts/weekly_summary.md` | 版本化提示词 |
| `apps/reporter/weekly.py` | 查库 → 评分 → 合并 → 抽取 → 渲染 `weekly-brief.md.j2` |
| `scripts/verify-plan-001e.sh` | 专项验证 14 项 |
| `packages/source_adapters/{company_ir,sec_edgar}/adapter.py` | RSS/SEC 请求超时容错 |

## 验证结果

| # | 项 | 结果 | 备注 |
| --- | --- | --- | --- |
| V1 | verify-plan-001e | 14/14 PASS | |
| V2 | pytest scoring + merge + weekly | 12/12 PASS | 含 III 期 significance≥0.80、多源合并 |
| V3 | 同一读出多源 | PASS | 2 事件 → 1 组，2 条 Evidence |
| V4 | III 期读出样例 | PASS | `significance_label` = 高 |
| V5 | 端到端周报 | PASS | `generate_weekly_brief` 产出中文 Markdown，pending 进「待核实」 |
| V6 | LLM Schema 不合规 | PASS | `ValidationError` → `use_llm=False` 规则降级 |
| V7 | ruff + mypy | PASS | |
| V8 | verify-plan-001d 回归 | 13/13 PASS | 含 RSS 超时单测 |

## 周报行为说明

- **关键结论**：仅 `medical_review_status=approved` 事件进入 §1；MVP 默认 pending 列「待核实」。
- **LLM**：无 `OPENAI_API_KEY` 或输出不合 Schema 时自动规则抽取，不阻断周报。
- **三分数**：分列写入 Event，禁止合并为单一分数（符合 AGENTS.md 红线）。

## 已知限制

- 跨源合并键依赖 `asset_id`/`indication_id` 落库质量；未解析资产时可能无法合并。
- LLM 抽取为可选增强，生产需配置 `OPENAI_API_KEY`。
- Obsidian frontmatter 导出、审核状态回写未在本期实现。

## 遗留问题与下阶段输入

- [ ] 周报 Markdown → Obsidian Vault 导出格式对齐 → **001f**
- [ ] `review_status` 审核回写数据库路径 → **001f**
- [ ] 定时采集 + 告警 + 覆盖率评估 → **001f**
