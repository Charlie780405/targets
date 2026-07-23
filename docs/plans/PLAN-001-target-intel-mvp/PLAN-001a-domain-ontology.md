# PLAN-001a: 产品与本体（第1周）

## 父纲领进度

父纲领 [PLAN-001](PLAN-001-target-intel-mvp.md)。本子计划为首个，无上游缺口。

## 目标

锁定首发靶点与适应症，建立领域模型（Pydantic + SQLAlchemy）、种子数据（靶点别名/药物/公司/适应症）、事件 Schema 与建库迁移，并搭出可渲染空数据的周报模板骨架。这是全系统地基。

## 依赖

- 纲领 §D1 已锁定 **IL-4Rα + AD/CSU/PN**；种子 YAML 已就位（`config/targets/il4ra.yaml`、`config/indications/*.yaml`、`config/assets-seed.yaml`、`config/orgs-seed.yaml`）。本期任务是写读取/建库代码，不需再决策靶点。

## Out of Scope

- 任何真实采集（留给 001b+）。
- 评分逻辑实现（留给 001e，本期只定枚举与字段）。
- 向量检索、pgvector。

## 关键决策

| # | 决策 | 理由 |
| --- | --- | --- |
| D1 | ORM 用 SQLAlchemy 2.0 + Alembic | 便于 SQLite→PostgreSQL 迁移 |
| D2 | 领域枚举集中在 `packages/domain` | 避免硬编码，作 SSOT |
| D3 | 种子用 YAML 放 `config/` | 非工程人员也能维护靶点词典 |

## 交付物 / 变更文件清单

| 路径 | 操作 | 用途 |
| --- | --- | --- |
| `packages/domain/models.py` | 新增 | Target/Asset/Organization/Indication/Trial/Publication/Conference/SourceDocument/Event/Evidence/Report 模型 |
| `packages/domain/enums.py` | 新增 | event_type/result_direction/phase/review_status/evidence_level 枚举 |
| `packages/entity_resolution/target_dictionary.py` | 新增 | 靶点别名归一（读 config/targets） |
| `config/targets/<target>.yaml` | 新增 | 首发靶点别名表（canonical/aliases/exclude_patterns） |
| `config/indications/*.yaml` | 新增 | 2–3 个适应症种子 |
| `config/assets-seed.yaml`、`config/orgs-seed.yaml` | 新增 | 药物/公司种子 |
| `migrations/` (Alembic) | 新增 | 首个迁移，建全部表 |
| `templates/weekly-brief.md.j2` | 新增 | 周报模板骨架（9 段结构，渲染空数据不报错） |
| `tests/test_domain_models.py`、`tests/test_target_dictionary.py` | 新增 | 模型往返 + 别名归一测试 |
| `scripts/verify-plan-001a.sh` | 新增 | 专项验证 |

## 靶点别名表示例（config/targets/il4ra.yaml）

```yaml
target_id: TGT_001
canonical_name: IL-4Rα
aliases: [IL4R, "IL-4 receptor alpha", CD124, "interleukin-4 receptor subunit alpha"]
exclude_patterns: []
indications: [atopic_dermatitis, csu, prurigo_nodularis]
```

## 验证清单

| # | 步骤 | 预期 |
| --- | --- | --- |
| V1 | `bash scripts/verify-plan-001a.sh` | 全 PASS（模型/枚举/种子/迁移/模板存在） |
| V2 | `alembic upgrade head`（SQLite） | 建表成功 |
| V3 | `pytest -q tests/test_domain_models.py tests/test_target_dictionary.py` | 通过 |
| V4 | 别名归一：输入 `CD124`→输出 `IL-4Rα` | 命中 |
| V5 | 周报模板渲染空数据 | 不报错 |
| V6 | `ruff check . && mypy .` | 零错误 |

## 遗留 / 下阶段输入

- 001b 需要：Trial 模型字段清单与 `content_hash` 规则（本期定稿）。
