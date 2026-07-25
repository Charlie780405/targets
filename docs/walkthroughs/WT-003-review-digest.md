# WT-003: 审核队列与研判摘要

对应 [PLAN-003](../plans/PLAN-003-review-digest/PLAN-003-review-digest.md)。

## 执行摘要

- **审核队列 Top-10**：按 `relevance_profile.yaml` 管线词（Dupilumab/III 期等）排序导出 Vault
- **AIT 综述降权**： allergen immunotherapy 类不再占唯一席位
- **publish 前全量评分** + **已审核文献摘要** Dashboard
- **LLM enrich**：`publish --enrich-publications --use-llm`

## 验证

| # | 项 | 结果 |
| --- | --- | --- |
| V1 | verify-plan-003 | PASS |
| V2 | Vault 06-Publications | 10 篇 Dupilumab/IL-4R 相关 |
| V3 | 待审队列表格 | 列对齐，含相关度 |

## 使用

```bash
python3 -m apps.reporter.publish --vault ./vault --enrich-publications --use-llm
python3 -m apps.reporter.review_sync --vault ./vault   # Obsidian 改 status 后
```

审核通过后查看 `00-Dashboard/已审核文献摘要.md`。

## 纳入教训（Vault 同步）

- **Skill**：`.cursor/skills/target-intel-vault-sync/SKILL.md` — Windows `git pull` / 禁止 `stash -u` / 关 Obsidian 再 pull
- Vault 仓库须含 `.gitignore`（`.obsidian/`），由 `ensure_vault_gitignore()` 在 publish 时写入
- 用户手改 `00-Dashboard/*` 会导致 pull 冲突 → 一律 `git restore` 后以服务器为准
