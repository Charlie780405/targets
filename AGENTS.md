# AGENTS.md — 靶点情报引擎 · 工程代理规则（仓库级持续指导）

本文件是 Codex / Cursor Agent 在本仓库工作的**固定工程规则**。每次开工先读本文件与 `docs/agent-context/workflow.md`。
可复用的数据接入 / 报告工作流后续封装为 Skill；本文件承载稳定的仓库级约束。

## 0. 一句话定位

系统的产品单位是**事件**（Event），不是文章。任何采集、抽取、报告都最终服务于「产出可追溯、可决策的事件与周报」。

## 1. 红线（违反任一条视为未完成）

1. **绝不提交密钥与运行时数据**：`.env*`、`*.pem/*.key`、`data/raw/**`、`data/logs/**`、`*.sqlite`、Vault 内容一律不入库。
2. **每条事件必须可追溯**：无原始 URL + 来源名称 + 证据片段 + 内容哈希的「事件」不得写入库、不得进周报。
3. **无人工审核不出医学结论**：`medical_review_status != approved` 的事件不得作为周报的「关键结论」发布（可列为「待核」）。
4. **证据分离评分**：`importance_score` / `confidence_score` / `novelty_score` 必须分列存储，禁止合并成单一分数。
5. **精确提交**：`git add <路径>`，禁止 `git add .`；仅在用户明确要求时 commit/push。
6. **PLAN / verify / 代码同批入库**：文档与实现一起提交，不得事后补。

## 2. 工程约定

- 语言 Python 3.12+。类型用 Pydantic v2 建模；对外/落库边界必须校验，内部信任。
- 采集优先级：**官方 API > RSS/结构化页面 > 稳定网页抓取 > 搜索引擎发现**。能用 API 绝不写爬虫。
- 网页自动化（Playwright）仅在无 API/RSS 时启用，且封装进对应「适配器」，不做通用爬虫。
- 每个数据源 = 一个 `packages/source_adapters/<source>/` 适配器，实现统一接口：`fetch() -> list[SourceDocument]`。
- **禁止硬编码**靶点名、来源名、事件类型、评分权重等口径值——一律引用 `config/` 下 SSOT 或 `packages/domain` 枚举。
- 抓取必须礼貌：遵守 `HTTP_MAX_RPS`、带 `User-Agent`、尊重 robots 与各源许可；付费墙全文不抓。

## 3. 测试与验证命令

```bash
# 单测（真实 HTTP 用 VCR.py 录制回放，禁止测试打真实外网）
pytest -q

# 静态检查
ruff check .
mypy .

# PLAN 专项验证（每个 PLAN 一支）
bash scripts/verify-plan-XXX.sh

# PLAN 目录布局校验（提交前）
bash scripts/validate-plan-dir-layout.sh
```

新增数据源适配器**必须**附带 VCR cassette 与去重/字段差异测试。

## 4. 医学证据要求（详见 `docs/medical-review-rules.md`）

- 结论级输出必须给出证据链：`ClinicalTrials.gov / PubMed / 公司稿 / 大会摘要` 至少一条一手来源。
- 「记录更新」≠「医学意义进展」：字段 diff 必须翻译成事件类型后才计入情报。
- 中文输出，**保留英文原始证据片段**（标题、终点、数值原文）。
- 不确定必须显式标注（`confidence_score` + 文字「待核实/单一来源」）。

## 5. 目录职责

| 目录 | 职责 |
| --- | --- |
| `apps/collector` | 调度与运行各源适配器，落原始 `SourceDocument` |
| `apps/processor` | 清洗、实体解析、去重、版本 diff、生成 `Event`、评分 |
| `apps/reporter` | 日报/周报生成、Obsidian Markdown 导出、邮件/网页 |
| `packages/domain` | 领域模型与枚举（Event/Target/Asset/... 的 SSOT） |
| `packages/source_adapters` | 各数据源适配器 |
| `packages/entity_resolution` | 靶点词典、药物解析、公司归一 |
| `packages/obsidian_exporter` | Vault frontmatter 与目录写入 |
| `config/` | 靶点别名、适应症、来源白名单/证据等级（YAML SSOT） |
| `prompts/` | LLM 抽取/摘要提示词（版本化） |
| `docs/` | 规格、agent-context、plans、walkthroughs |

## 6. 交付流程（简版，完整见 `docs/agent-context/workflow.md`）

```
需求澄清 → PLAN(±子计划) → 用户确认 → feat 分支 → 实现 → verify → 精确 commit
    → merge main(--no-ff) → (用户要求才 push/部署) → WT 验收
```

- PLAN 全部放 `docs/plans/PLAN-XXX-<slug>/`（禁止根目录散落）。
- 每 PLAN 一支 `scripts/verify-plan-XXX.sh`，结束打印 `pass/total`。
- WT 放 `docs/walkthroughs/WT-XXX-<slug>.md`，逐条回填 PLAN 验证清单。
