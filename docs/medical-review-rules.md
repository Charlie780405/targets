# 医学审核规则 · medical-review-rules

> 目标：产出 **CMO / BD / 临床开发决策级** 输出，而非信息摘要。无人工审核不出医学结论。

## 1. 事件评分机制（先规则，后模型）

```
总分 =
  来源可靠性 × 25%
+ 医学重要性 × 30%
+ 新颖性     × 20%
+ 靶点相关性 × 15%
+ 时间敏感性 × 10%
```

**三分数分列存储**（禁止合并）：

| 分数 | 回答 | 说明 |
| --- | --- | --- |
| `significance_score` | 这事重不重要 | III 期读出、监管决定、安全信号、大额交易… |
| `confidence_score` | 判断可不可靠 | 来源等级 + 交叉验证数 |
| `novelty_score` | 是不是真新增 | 与既往事件去重比对 |

「重要但未经证实」与「可靠但无关紧要」不能混成一个分数。

## 2. 典型高分（significance=high）事件

- III 期达到 / 未达到主要终点
- 监管批准、拒绝、突破性疗法认定
- 重要安全性信号
- 大型授权 / 交易
- 首次人体概念验证（FIH PoC）
- 竞争产品终止开发

## 3. 「记录更新」≠「医学进展」

临床试验字段 diff 必须先翻译成事件类型再计分。示例：

| 字段变化 | 是否成事件 | 事件类型 |
| --- | --- | --- |
| Overall Status: Recruiting→Completed | 是 | trial_change（可能预示读出临近） |
| Results Posted: No→Yes | 是（高） | clinical_result |
| Enrollment 小幅修订 | 通常否 | — |
| Primary Completion Date 提前/推迟 | 是 | trial_change |
| Sponsor 变更 | 是 | trial_change / deal 线索 |

## 4. 人工审核状态机

```
pending ──(审核通过)──▶ approved      # 可作周报关键结论
   │
   ├──(证据不足)─────▶ needs_info    # 回采/补证据后重审
   └──(不成立/误报)──▶ rejected      # 不进周报，保留记录供去重
```

**发布门槛**：只有 `approved` 事件可作为周报「本周关键结论」；`pending` 可列「待核实」区，`rejected` 不出现。

## 5. 证据要求

- 结论级输出必须有证据链，至少 1 条 A/B/C 级来源（见 `source-registry.md`）。
- 中文输出，**保留英文原始证据片段**（终点名称、数值、结论原文），便于人工复核。
- 不确定显式标注：`confidence_score` + 文字（「单一来源」「待官方确认」「摘要未含数值」）。
- 交叉验证：高 significance 事件尽量 ≥2 来源；来源冲突时以证据等级高者为准并标注分歧。

## 6. 审核工作面

人工审核在 **Obsidian** 完成（事件卡片 frontmatter 的 `review_status`）。审核动作回写数据库为 SSOT；Obsidian 是研判界面，不是调度/存储主库。

## 7. 审计与可追溯

每条事件保留 `content_hash` 与版本、`discovered_at`、来源 `fetched_at`。审核人可回溯到原始快照（`data/raw/`）验证证据未被 LLM 篡改。
