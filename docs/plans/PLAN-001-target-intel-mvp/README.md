# PLAN-001 · 靶点情报引擎 MVP（纲领目录）

本目录存放纲领与全部子计划。引用路径统一从此目录展开。

| 编号 | 文件 | 对应周 | 交付物 | 状态 |
| --- | --- | --- | --- | --- |
| 001（纲领） | [PLAN-001-target-intel-mvp.md](PLAN-001-target-intel-mvp.md) | — | 总纲领、里程碑、累积缺口表 | 已确认（D1=IL-4Rα 已锁定） |
| 001a | [PLAN-001a-domain-ontology.md](PLAN-001a-domain-ontology.md) | 第1周 | 领域模型、靶点/药物/公司/适应症种子、事件 Schema、周报模板骨架 | 已合并 `1e78ac4` |
| 001b | [PLAN-001b-trial-collection.md](PLAN-001b-trial-collection.md) | 第2周 | ClinicalTrials.gov 适配器、Trial 表、版本快照与字段 diff、trial_change 事件 | 已合并 `e8ba45d` |
| 001c | [PLAN-001c-publication-collection.md](PLAN-001c-publication-collection.md) | 第3周 | PubMed 适配器、检索式、PMID/DOI 去重、摘要级抽取、勘误/撤稿 | 已合并 `af900e5` |
| 001d | [PLAN-001d-company-finance.md](PLAN-001d-company-finance.md) | 第4周 | 公司 IR/RSS 适配器、SEC/交易所公告、实体匹配、来源可靠性评分 | 已合并 `dde87f4` |
| 001e | [PLAN-001e-intelligence-scoring.md](PLAN-001e-intelligence-scoring.md) | 第5周 | 事件分类、三分数评分、跨来源合并、LLM 结构化抽取、周报生成 | 进行中 |
| 001f | [PLAN-001f-obsidian-ops.md](PLAN-001f-obsidian-ops.md) | 第6周 | Vault 模板、Markdown 发布器、Git 同步、定时任务、告警、覆盖率评估 | 待启动 |

## 使用方式

1. 用户确认纲领与首发靶点决策（见纲领 §关键决策 D1）。
2. 逐周开 `feat/PLAN-001x-<slug>` 分支实现，每子计划独立 verify + WT。
3. 开下一子计划前，读上一 WT 的「遗留与下阶段输入」，回填纲领 §累积缺口表。
