# Target Intelligence Engine（靶点情报引擎）

> 以**事件**为核心单位的自免靶点情报系统：云端持续采集 → 结构化处理与实体解析 → 事件数据库 → 情报评分与研判 → Obsidian 研判 + 周报。

- **仓库**：https://github.com/Charlie780405/targets
- **域名**：targets.qyunsgen.com
- **定位**：可独立运行的「靶点情报引擎」，未来并入「医学研发工作台」。
- **架构方针**：本地优先、云端采集、Obsidian 研判、Codex 开发维护的**混合架构**。

## 系统单位：不是「文章」，而是「事件」

一条事件 = 类型 + 靶点/药物/公司/适应症 + 时间 + 结果方向 + 重要性 + **可追溯证据**。
第一版建立六类事件：临床试验变化、临床结果、监管动态、论文/预印本、投融资/授权/并购、大会摘要。

## 架构总览

```
数据源 → 采集层(API/RSS/定向抓取) → 处理层(清洗/实体识别/去重/版本比较)
→ 事件数据库(SQLite→PostgreSQL) → 情报层(分类/评分/总结/交叉验证)
→ Obsidian Vault(研判) + 日报/周报(Markdown/邮件/网页)
```

## 快速导航

| 我想… | 去读 |
| --- | --- |
| 了解 Agent/Codex 工程规则 | [`AGENTS.md`](AGENTS.md) |
| 了解交付流程（PLAN→实现→verify→WT） | [`docs/agent-context/workflow.md`](docs/agent-context/workflow.md) |
| 了解产品与 MVP 边界 | [`docs/product-spec.md`](docs/product-spec.md) |
| 了解事件数据模型 | [`docs/event-schema.md`](docs/event-schema.md) |
| 了解数据源与证据等级 | [`docs/source-registry.md`](docs/source-registry.md) |
| 了解医学审核规则 | [`docs/medical-review-rules.md`](docs/medical-review-rules.md) |
| 了解报告风格 | [`docs/reporting-style.md`](docs/reporting-style.md) |
| 看开发纲领与路线 | [`docs/plans/PLAN-001-target-intel-mvp/`](docs/plans/PLAN-001-target-intel-mvp/) |

## 目录结构

```
apps/{collector,processor,reporter}   # 采集 / 处理 / 报告三应用
packages/{domain,source_adapters,entity_resolution,obsidian_exporter}
config/{targets,indications,sources}  # 靶点别名表、适应症种子、来源白名单
prompts/  templates/  migrations/  tests/  scripts/  docs/
data/{raw,logs}                       # 运行时原始数据与日志（不入库）
```

## 环境

Python 3.12+（本机实测 3.14）。开发流程见 `docs/agent-context/workflow.md`。
