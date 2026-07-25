# PLAN-002c: LLM 文献提炼

## 目标

对 pending 的 publication 事件生成中文分析（关联度、要点、局限），写入 SourceDocument.payload_json.analysis；导出时展示「研判草稿」；**不得**自动 approved。

## 交付物

| 路径 | 用途 |
| --- | --- |
| `prompts/publication_analysis.md` | LLM 提示词 |
| `apps/processor/publication_analysis.py` | 抽取 + 规则降级 |
| `apps/collector/run_publication_enrich.py` | 批量 enrich CLI |

## 验证

`bash scripts/verify-plan-002c.sh`
