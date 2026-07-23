# 产品规格 · Target Intelligence Engine

## 1. 产品定位

一个可独立运行的**靶点情报引擎**：把散落在临床试验库、文献、公司公告、大会、监管渠道的信息，转成**结构化、可追溯、可决策的「事件」**，并以周报交付到 CMO/BD/临床开发级读者。未来并入「医学研发工作台」。

**首个里程碑不是「抓了一万条」，而是**：连续四周产出周报，重要事件漏报率可接受、重复率低、每条关键结论可追溯，并确实节省医学情报整理时间。

## 2. 核心单位：事件（Event）

系统的产品单位是**事件**，不是文章。六类事件（第一版）：

1. 临床试验新增或状态变化
2. 临床结果披露
3. 监管动态
4. 论文及预印本
5. 投融资、授权合作与并购
6. 医学大会摘要 / 壁报 / 口头报告

每条事件必须保留：原始 URL、来源名称、发布时间与抓取时间、原始标题与证据片段、靶点/药物/公司/适应症、系统判断结果、人工审核状态、内容哈希与版本、与既往事件的关联。详见 `event-schema.md`。

## 3. 技术难点排序（决定投入重心）

```
实体解析 > 版本变化识别 > 来源覆盖 > 证据校验 > 摘要生成
```

LLM 摘要**不是**最难的部分。三个核心技术模块（详见各文档）：

- **靶点词典**（`entity_resolution`）：基因名/蛋白名/CD 编号/历史名/通路名/大小写连字符变体归一。
- **药物实体解析**：研发代码 ↔ 通用名 ↔ 公司 ↔ 靶点 ↔ 机制，避免同一资产被当成多个药物。
- **版本差异检测**：比较两次抓取的字段（Overall Status / Enrollment / Primary Completion Date / Outcomes / Results Posted / Sponsor / Locations），把「记录更新」翻译成「医学意义进展」。

## 4. MVP 边界

### 只做

- **1 个靶点**（见 §5 决策）
- **2–3 个自免适应症**
- 数据源：ClinicalTrials.gov、PubMed；10–20 家公司 IR 页面；1 个重点医学大会
- **周报**（不做日报）
- 中文输出，保留英文原始证据
- **人工审核后发布**

### 暂时不做

全互联网通用爬虫、所有自免靶点、自动付费墙全文抓取、复杂知识图谱前端、自建大模型、一开始就做 Obsidian 插件、无人工审核的自动医学结论、依赖搜索结果摘要作为证据。

## 5. 关键决策：首发靶点与适应症（已锁定）

> 这是 MVP 的地基，直接决定 `config/targets` 与 `config/indications` 种子。

**已锁定：**

| 项 | 取值 | 理由 |
| --- | --- | --- |
| 首发靶点 | **IL-4Rα** | dupilumab 生态最活跃，跨适应症事件量足够「养」管线；用户可亲自判断输出质量 |
| 适应症 | **特应性皮炎(AD) / 慢性自发性荨麻疹(CSU) / 结节性痒疹(PN)** | 均自免/免疫炎症，来源丰富，与既往 CSU 调研衔接 |

种子文件：`config/targets/il4ra.yaml`、`config/indications/{atopic_dermatitis,csu,prurigo_nodularis}.yaml`、`config/assets-seed.yaml`、`config/orgs-seed.yaml`。

**备选（已记录，暂不采用）**：若日后更聚焦 CSU，可切 **BTK**（remibrutinib 等）或 **KIT**（barzolvolimab）。CSU 竞争靶点（BTK/KIT/IgE）已在 `config/indications/csu.yaml` 备注为交叉关注对象。

## 6. 部署形态：混合架构

| 层 | 位置 | 内容 |
| --- | --- | --- |
| 采集 / 处理 / 报告 | **云端 Vultr** | 定时采集、PostgreSQL、原始数据与日志、LLM 抽取、周报生成 |
| 研判 | **本地** | Obsidian Vault、人工医学审核、深度分析、Codex 开发环境、Git |

同步（第一版极简）：云端生成 Markdown → push 私有 Git 仓库 → 本地 Obsidian 拉取。敏感 Vault 不进普通云同步，用私有仓库 + 加密备份 + 最小权限密钥。

## 7. 成功度量（MVP 验收）

| 指标 | 目标（MVP） |
| --- | --- |
| 周报连续产出 | ≥ 4 周不断档 |
| 重要事件漏报率 | 可接受（人工回溯抽检） |
| 重复事件率 | 低（去重有效） |
| 关键结论证据可追溯率 | 100% |
| 是否节省整理时间 | 用户主观确认「是」 |

## 8. 技术栈

Python 3.12 / FastAPI / httpx + feedparser + selectolax /（必要时）Playwright / Pydantic / APScheduler（正式版可 Prefect）/ SQLite→PostgreSQL / Alembic / PostgreSQL FTS /（二阶段）pgvector / Jinja2 / Obsidian Markdown / Git / pytest + VCR.py / Docker Compose / 结构化日志 + Sentry 或邮件告警。
