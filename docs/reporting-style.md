# 报告风格 · reporting-style

> 日报与周报**分开设计**。MVP 只做周报。中文输出，保留英文原始证据。

## 1. 日报（MVP 暂不做，接口预留）

只回答「发生了什么」，长度 3–10 条：

- 新增高价值事件
- 临床试验关键字段变化
- 新发表论文
- 公司/监管公告
- 需人工复核的异常

## 2. 周报（MVP 交付物）

回答「这意味着什么」。**不是日报拼接**：须合并重复事件并做分析。固定结构：

1. 本周关键结论（仅 `approved` 事件，每条带证据链接）
2. 靶点级动态
3. 药物与公司动态
4. 临床试验变化
5. 论文与大会数据
6. 竞争格局变化
7. 对自免适应症开发的影响
8. 下周观察点
9. 证据与不确定性（列 `pending` / 单一来源 / 分歧项）

周报须回答：是否改变靶点验证程度？是否改变同类药竞争排序？是否出现安全性/疗效信号？是否影响适应症选择？是否形成 BD/投资/临床开发机会？（延续「CMO/BD 决策级」输出定位。）

## 3. 每条关键结论的写法

```
【结论】一句话医学/BD 判断（中文）
【依据】英文原始证据片段（终点/数值/结论原文）
【来源】source_name + URL（≥1 条 A/B/C 级）
【置信】confidence 分档 + 不确定性说明
【影响】对靶点/竞争/适应症/BD 的含义
```

## 4. 模板与产出

- 模板：`templates/weekly-brief.md.j2`（Jinja2）。
- 产出：Markdown → 导出到 Obsidian `09-Weekly-Briefs/` → 可选邮件/网页。
- 人工审核通过后发布（见 `medical-review-rules.md`）。

## 5. Obsidian Vault 目录（研判界面）

```
Target-Intelligence/
├── 00-Dashboard/
├── 01-Targets/       靶点知识主页
├── 02-Assets/        药物档案
├── 03-Companies/
├── 04-Indications/
├── 05-Trials/
├── 06-Publications/
├── 07-Events/{Clinical,Financing,Congress,Regulatory}/
├── 08-Daily-Briefs/
├── 09-Weekly-Briefs/
├── 10-Source-Documents/
└── 99-Templates/
```

Obsidian 负责：人工审核、靶点/药物/公司档案、事件卡片、周报、双向链接、Dataview 查询、长期知识沉淀。
**不**负责：定时调度、大量原始存储、复杂事务、爬虫状态、去重并发控制。

- Vault API：https://docs.obsidian.md/Reference/TypeScript+API/Vault
- 插件开发：https://docs.obsidian.md/Plugins/Getting+started/Build+a+plugin （MVP 不做插件；插件开发须在独立测试 Vault，避免损坏主库）

## 6. 语言约定

- 正文中文；证据片段、终点名、药名代码保留英文原文。
- 数值必须带单位与统计口径（如 EASI-75、p 值、置信区间原文），不做二次换算。
