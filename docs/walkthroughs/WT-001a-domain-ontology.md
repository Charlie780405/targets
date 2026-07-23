# WT-001a: 领域模型与靶点词典

对应 [PLAN-001a](../plans/PLAN-001-target-intel-mvp/PLAN-001a-domain-ontology.md)。合并 commit: `1e78ac4`（feat: `43f0fdf`）。

## 执行摘要

- **目标**：建立领域模型（Pydantic/SQLAlchemy）、靶点词典、Alembic 首版迁移、周报模板骨架。
- **涉及文件**：21 个新增文件，+1264 行。
- **关键能力**：12 表 ORM、IL-4Rα 别名归一、空数据周报渲染、verify-plan-001a 专项脚本。

## 变更明细

| 文件 | 摘要 |
| --- | --- |
| `packages/domain/{enums,models,database,content_hash}.py` | 领域枚举、12 表模型、SQLite 引擎、content_hash |
| `packages/entity_resolution/target_dictionary.py` | 读取 `config/targets/*.yaml`，别名→canonical |
| `migrations/versions/001_initial_schema.py` | Alembic 首版建表 |
| `templates/weekly-brief.md.j2` + `apps/reporter/weekly_template.py` | 周报 9 段 Jinja2 模板 |
| `tests/test_{domain_models,target_dictionary,weekly_template}.py` | 单元测试 |
| `scripts/verify-plan-001a.sh` | 专项验证 19 项 |

## 验证结果

| # | 项 | 结果 | 备注 |
| --- | --- | --- | --- |
| V1 | verify-plan-001a | 19/19 PASS | |
| V2 | alembic upgrade head | PASS | SQLite |
| V3 | pytest | 9/9 PASS | |
| V4 | CD124→IL-4Rα | PASS | |
| V5 | 空数据周报渲染 | PASS | |
| V6 | ruff + mypy | PASS | |

## 回归确认

- 纲领级 verify-plan-001（30/30）仍适用；001a 为增量交付，未破坏 PLAN-001 脚手架。

## 已知限制

- 种子数据（YAML）已就位，**尚未**写入数据库 seed 脚本（001b 采集时自然落库）。
- 周报模板仅骨架，尚无真实事件数据填充（001e）。

## 遗留问题与下阶段输入

- [x] Trial 字段清单与 `content_hash` 规则已定稿 → **001b 可直接使用**（`Trial` + `TrialSnapshot.watch_fields_hash`）
- [ ] 公司 IR URL 白名单 `rss_url` 多数为 null → **001d 逐个核实填入**
- significance 初判规则 → **001e**
