# PLAN-004: 审阅回写与 LLM 发布自动化

## 目标

用户在 Obsidian 完成 `review_status` 审阅后，**无需 SSH 手敲多条命令**，服务器自动 pull Vault → sync DB → LLM 摘要 → 更新 Dashboard/周报并 push。

## 根因（2026-07-25）

| 现象 | 根因 |
| --- | --- |
| `已审核文献摘要` 仍「暂无 approved」 | 审阅只改本地 Vault，**未 push** 或服务器 **未 pull + review_sync** |
| 周报无关键结论 | DB `medical_review_status=approved` 为 0；周报 §1 只读 approved |
| 摘要是规则降级 | systemd `publish` **未传 `--use-llm`**；默认 `use_llm=False` |
| 本地/服务器来回切 | 缺 **一键 pipeline** 与 **Vault 变更轮询 timer** |

## 交付

| 编号 | 内容 |
| --- | --- |
| 004a | `vault_publish_pipeline.py` + `scripts/vault-sync-publish.sh` |
| 004b | systemd `target-intel-vault-sync.timer`（每 10min 检测 Vault 远程变更） |
| 004c | 周报 timer 改用 pipeline；`.env` 中 `PUBLISH_USE_LLM=true` |
| 004d | Skill 更新：本地仅「审阅 + Obsidian Git push」 |

## Out of Scope

- Codex 桌面端远程操控（不推荐；用 Git + timer 更稳）
- 双向实时 sync（仍 Git 为 SSOT）

## 用户侧（一次性配置）

1. Obsidian 安装 **Obsidian Git** 插件，设置 save 后 auto commit/push `06-Publications/`
2. 服务器 `.env`：`OPENAI_API_KEY=...`、`PUBLISH_USE_LLM=true`
3. `bash scripts/install-vultr-user-systemd.sh` 重装 timer

## 验证

- V1：`pytest tests/test_vault_publish_pipeline.py`
- V2：本地 push 一条 `approved` → 10min 内服务器 Dashboard 更新
- V3：`journalctl --user -u target-intel-vault-sync` 无 ERROR
