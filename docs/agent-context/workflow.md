# 交付工作流（PLAN → 实现 → verify → WT）

> 本文改编自 qyunsgen 团队 `plan-implement-deploy-workflow` 骨架，适配本仓库的 **Python + 混合部署（云端采集 / 本地研判）** 形态。
> qyunsgen 特有的 Prisma / docker-build.sh / Oracle ARM64 等步骤在此**不适用**，替换为 Python + Alembic + Docker Compose + Vultr。

## 阶段总览

```
需求澄清 → PLAN(±子计划) → 用户确认 → feat 分支 → 实现 → verify(pytest+ruff+mypy+专项)
    → 精确 commit → merge main(--no-ff) → (用户要求才 push / 部署 Vultr) → WT 验收
```

**红线（违反任一条禁止写 WT「已部署」）：**

1. `git status` 非 clean 不得生产部署。
2. 功能必须在 `main` 有 commit（`git log main..feat/XXX` 为空）。
3. git HEAD = 镜像 tag/sha = 服务 `/health` 版本，三方一致。
4. PLAN / WT / verify 脚本与代码**同批**入库。
5. 精确 `git add <路径>`，禁止 `git add .`；仅在用户明确要求时 commit/push。

## 阶段 1：PLAN

### 计划粒度

| 规模 | 做法 |
| --- | --- |
| 小（单模块、<200 行） | 单文件 `docs/plans/PLAN-XXX-<slug>/PLAN-XXX-<slug>.md` |
| 大（多模块 / 架构） | 先写**纲领** `PLAN-XXX-<slug>.md`，再拆子计划 `PLAN-XXXa/b/c…` 同目录 |

**存放规范：**

1. 所有 PLAN 都放 `docs/plans/PLAN-XXX-<slug>/`（含单文件与纲领+子计划）。
2. 目录名 = `PLAN-XXX-<slug>`（编号 + 纲领 slug）。
3. **禁止**在 `docs/plans/` 根目录散落任何 `PLAN-*.md`。
4. WT 在 `docs/walkthroughs/WT-XXX-<slug>.md`；verify 在 `scripts/verify-plan-XXX.sh`。
5. 提交前跑 `bash scripts/validate-plan-dir-layout.sh`。

### PLAN 必含章节

目标 / 依赖 / Out of Scope / 关键决策 / 子计划表 / 变更文件清单 / 验证清单(V1..Vn) / 回滚预案 / 影响范围。
纲领另含「子计划索引 + 累积缺口登记表」；连续子计划另含「上一子计划缺口分析」。

### 用户确认

非 hotfix：**用户确认 PLAN 后再编码**。规划模式只读时只输出 PLAN。

## 阶段 2：分支与实现

```bash
git checkout main
git checkout -b feat/PLAN-XXX-<slug>
```

实现原则：最小 diff；改公共函数/类型前先 `rg` 查引用；口径值引用 `config/` 或 `packages/domain` SSOT，禁止硬编码；每改一批跑 `ruff check` + `mypy`。

## 阶段 3：验证

层次（自下而上）：

1. 专项脚本 `scripts/verify-plan-XXX.sh`（优先，打印 `pass/total`）。
2. `pytest -q`（新数据源必须有 VCR cassette）。
3. `ruff check .` + `mypy .`。
4. 部署后 `/health` 与烟囱脚本。

PLAN 的 V1..Vn 须在 WT 中逐条回填（通过 / 失败原因）。

## 阶段 4：提交与合并

```bash
git status && git diff
pytest -q && ruff check . && mypy .

git add docs/plans/PLAN-XXX-*/ docs/walkthroughs/WT-XXX-*.md \
        scripts/verify-plan-XXX.sh <改动的 .py 文件>

git commit -m "$(cat <<'EOF'
feat(scope): 简短中文描述

- 改动点 1
- 改动点 2

对应 PLAN-XXX
EOF
)"

git checkout main && git merge --no-ff feat/PLAN-XXX-<slug> -m "merge: PLAN-XXX <slug>"
git log main..feat/PLAN-XXX-<slug>   # 必须无输出
```

**默认**：用户未明确要求 push/部署时，止步于 merge main，WT 不写「已部署」。

## 阶段 5：部署（Vultr，云端采集/报告；本地负责 Obsidian 研判）

```bash
git status --short          # 必须为空
git rev-parse --short HEAD  # 记 A

# Vultr 服务器
git pull origin main
docker compose --env-file .env up -d --build
curl -s http://localhost:8000/health   # 版本须 = A
```

- 采集/处理/报告用 cron 或 systemd timer 或 APScheduler 定时；不让交互式会话成为生产管线唯一依赖。
- 云端只产出 Markdown → push 到私有 Vault 仓库 → 本地 Obsidian 拉取研判。

## 阶段 6：Walkthrough

`docs/walkthroughs/WT-XXX-<slug>.md`，必含：执行摘要、变更明细、验证结果、回归确认、已知限制、遗留问题与下阶段输入（每条标注归并子计划）。

## 与 qyunsgen 骨架的差异对照

| qyunsgen | 本仓库 |
| --- | --- |
| Prisma migrate deploy | Alembic `alembic upgrade head` |
| `npx tsc --noEmit` | `ruff check` + `mypy` |
| `docker-build.sh` / Oracle ARM64 | `docker compose up --build`（Vultr amd64） |
| `verify-plan-033.sh` 烟囱 | `curl /health` + `verify-plan-001.sh` |
| Next.js `/api/health` | FastAPI `/health` |
