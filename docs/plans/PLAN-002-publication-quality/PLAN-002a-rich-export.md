# PLAN-002a: Obsidian 文献富导出

## 目标

Publication 事件笔记展示 PMID、DOI、发表日期、完整摘要与可点击链接；提供 `python3 -m apps.reporter.review_sync`。

## 交付物

| 路径 | 用途 |
| --- | --- |
| `packages/obsidian_exporter/publication_context.py` | Event→Publication 解析 |
| `packages/obsidian_exporter/exporter.py` | 扩展 frontmatter 与正文 |
| `apps/reporter/review_sync.py` | `__main__` CLI |
| `99-Templates/publication-event.md` | 导出时写入模板 |

## 验证

`bash scripts/verify-plan-002a.sh`
