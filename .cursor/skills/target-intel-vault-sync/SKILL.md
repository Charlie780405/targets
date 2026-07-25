---
name: target-intel-vault-sync
description: >-
  Target Intelligence Obsidian Vault 与 target-intel-vault 仓库的 Windows/本地同步与审核回写（无需用户 @）。
  自动适用于：git pull 失败、local changes overwritten、stash .obsidian Permission denied、
  06-Publications 删除失败、待审队列冲突、review_status 回写、Vault prune、OneDrive Obsidian 路径。
---

# Target Intelligence · Vault 同步与审核（Windows + 服务器）

## 架构（必记）

| 仓库 | 路径 | 职责 |
| --- | --- | --- |
| **targets** | 服务器 `/home/dev/Targets` | 采集、DB、publish 生成 Vault |
| **target-intel-vault** | 本地 Obsidian / 服务器 `./vault` | **仅** Markdown 研判面；服务器 `publish` 后 push |

**不要**在本地跑 `apps.reporter.publish`（DB 在服务器）。  
**不要**用 `git stash -u`（会碰 `.obsidian/`，Obsidian 打开必 Permission denied）。

## 自动生成的文件（不要手改）

- `00-Dashboard/待审队列.md`
- `00-Dashboard/已审核文献摘要.md`
- `09-Weekly-Briefs/*`（服务器生成）

**可改**：`06-Publications/*.md` 的 frontmatter **`review_status`**  only。

## Windows 拉取远程 Vault（标准流程）

**前置：完全退出 Obsidian**（任务管理器无 `Obsidian.exe`）。OneDrive 同步可先暂停 30s 若仍删不掉文件。

```cmd
cd C:\Users\Administrator\OneDrive\Obsidian\Target-Intelligence

git status

REM 丢弃服务器会覆盖的自动生成文件（不要用 stash -u）
git restore "00-Dashboard/待审队列.md" "00-Dashboard/已审核文献摘要.md"
git restore 06-Publications/

git pull
```

### 常见报错

| 现象 | 原因 | 处理 |
| --- | --- | --- |
| `local changes would be overwritten` | 本地改过 Dashboard / 旧 Publications | `git restore <路径>` 后重 pull |
| `Deletion of directory '06-Publications' failed` | Obsidian/OneDrive 占用 md | **关 Obsidian** → 对提示答 `y` 或再 `git pull` |
| `stash .obsidian Permission denied` | 用了 `git stash -u` | `git stash drop`（若有 WIP）→ 改用 **restore 指定目录**，见上 |
| pull 后仍见 100 篇旧文献 | 未 pull 成功或打开了旧缓存 | 确认 `git log -1` 与服务器一致；Obsidian 重开库 |

## 人工审核 → 回写服务器

1. Obsidian 打开 `06-Publications/`，改 `review_status`: `approved` | `rejected` | `needs_info`
2. **关 Obsidian** 后在本机 Vault 仓库：

```cmd
git add 06-Publications/
git commit -m "review: update publication statuses"
git push origin master
```

3. **服务器**（SSH）：

```bash
cd ~/Targets/vault && git pull
cd ~/Targets
python3 -m apps.reporter.review_sync --vault ./vault
python3 -m apps.reporter.publish --vault ./vault --enrich-publications --use-llm
```

4. 本地再 **关 Obsidian** → `git pull` → 查看 `00-Dashboard/已审核文献摘要.md`

## Agent 纪律

- 教用户同步时 **永远先给「关 Obsidian + restore + pull」**，禁止推荐 `git stash -u`
- 服务器 prune 后本地 pull **必然**删旧 `06-Publications/*.md`，属预期
- 用户只审 Top-N 队列；AIT 等弱相关不应再出现（PLAN-003 `relevance_profile.yaml`）
- 若需改队列口径，改 SSOT 后服务器 `publish`，不要本地手改 Dashboard

## 相关 SSOT

- `config/relevance_profile.yaml` — 审核队列 Top-N
- `config/publication_filter.yaml` — Vault 导出门槛
- `docs/walkthroughs/WT-003-review-digest.md`
