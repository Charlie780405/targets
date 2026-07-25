# PLAN-002 文献质量与研判

纲领：[PLAN-002-publication-quality.md](./PLAN-002-publication-quality.md)

## 执行顺序

**P0 → 002b（Vault 门外）** → 002a → 002c ∥ 002d

| 子计划 | 文件 | 说明 |
| --- | --- | --- |
| **002b** | [PLAN-002b-relevance-filter.md](./PLAN-002b-relevance-filter.md) | **优先**：弱相关挡在 Vault 外 |
| 002a | [PLAN-002a-rich-export.md](./PLAN-002a-rich-export.md) | 过线文献富导出 + review_sync CLI |
| 002c | [PLAN-002c-llm-analysis.md](./PLAN-002c-llm-analysis.md) | LLM 文献提炼 |
| 002d | [PLAN-002d-review-dashboard.md](./PLAN-002d-review-dashboard.md) | 待审 Dashboard + 周报去重 |

验证：`bash scripts/verify-plan-002.sh`
