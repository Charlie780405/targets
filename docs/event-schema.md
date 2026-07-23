# 事件数据模型 · event-schema

> 结构化数据库是系统主干，向量检索只是辅助（二阶段）。不要只依赖向量库。

## 1. 实体清单

```
Target        靶点
Asset         药物/资产
Organization  公司/机构
Indication    适应症
Trial         临床试验
Publication   论文/预印本
Conference    大会及其摘要
SourceDocument 原始抓取文档（含 URL、快照、哈希）
Event         事件（系统产品单位）
Evidence      证据（事件 ↔ 来源片段的多对多）
Report        日报/周报
```

## 2. 核心事件表

```sql
event
- id
- event_type            -- 见 §3 枚举
- target_id
- asset_id
- indication_id
- organization_id
- event_date            -- 事件发生/披露日期
- discovered_at         -- 系统发现时间
- title
- summary
- significance_score    -- 重要性（事件是否重要）
- confidence_score      -- 可靠性（判断是否可信）
- novelty_score         -- 新颖性（是否真正新增）
- medical_review_status -- pending / approved / rejected / needs_info
- source_count
- content_hash          -- 去重与版本
```

**三分数必须分列**：`significance`（重要但可能未证实）、`confidence`（可靠但可能无关紧要）、`novelty`（是否新增）不得合并。评分口径见 `medical-review-rules.md`。

## 3. 枚举（SSOT：`packages/domain`）

```
event_type:
  trial_change        临床试验新增/状态变化
  clinical_result     临床结果披露
  regulatory          监管动态
  publication         论文/预印本
  deal                投融资/授权/并购
  congress            大会摘要/壁报/口头报告

result_direction:     positive | negative | mixed | inconclusive | na
phase:                preclinical | phase_1 | phase_1_2 | phase_2 | phase_2_3 | phase_3 | phase_4 | na
medical_review_status: pending | approved | rejected | needs_info
```

## 4. 证据（Evidence）

事件与来源是**多对多**。每条 Evidence 保留：

```
evidence
- id
- event_id
- source_document_id
- source_name          -- clinicaltrials.gov / pubmed / company_release / congress ...
- source_url
- evidence_snippet     -- 英文原始片段（终点、数值、结论原文）
- evidence_level       -- 见 source-registry.md 证据等级
- published_at
- fetched_at
- content_hash
```

## 5. 版本差异（Trial 快照）

临床试验监测不能只看「最近更新」。每次抓取存一份快照，比较关键字段生成 `trial_change` 事件：

```
监测字段：Overall Status, Enrollment, Primary Completion Date,
         Study Completion Date, Outcome Measures, Results Posted,
         Sponsor, Locations
```

字段 diff → 判定是否「有医学意义的进展」→ 生成事件（非所有更新都成事件）。

## 6. Obsidian frontmatter（导出格式，SSOT 与 DB 对应）

```yaml
---
event_id: EVT-2026-00031
event_type: clinical_result
target: IL-4Rα
asset: ABC-101
indication: CSU
event_date: 2026-07-18
importance: high          # significance 的分档展示
confidence: 0.91
review_status: pending
sources:
  - clinicaltrials.gov
  - company_release
---
```

## 7. ID 规范

- `Event`：`EVT-<YYYY>-<5位序号>`（如 `EVT-2026-00031`）
- `Target`：`TGT_<3位>`（如 `TGT_001`）
- `Asset` / `Organization` / `Indication`：短稳定 slug 或前缀 ID，写入 `config/`。

## 8. 存储选型

| 阶段 | 主库 | 全文 | 向量 | 原始文件 |
| --- | --- | --- | --- | --- |
| 单机 MVP | SQLite / DuckDB | SQLite FTS5 | — | 本地目录 `data/raw/` |
| 云端正式 | PostgreSQL | PostgreSQL FTS | pgvector（二阶段） | 本地目录或 S3 兼容对象存储 |

迁移用 Alembic；ORM 用 SQLAlchemy 2.0（模型定义在 `packages/domain`）。
