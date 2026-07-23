# 数据源登记表 · source-registry

> 采集优先级：**官方 API > RSS/结构化页面 > 稳定网页抓取 > 搜索引擎发现**。
> 每个数据源 = `packages/source_adapters/<source>/` 一个适配器；来源白名单与证据等级用 `config/sources/*.yaml` 做 SSOT。

## 1. MVP 数据源

| 类别 | MVP 数据源 | 接入方式 | 说明 |
| --- | --- | --- | --- |
| 临床试验 | ClinicalTrials.gov API v2 | 官方 API + OpenAPI | 最先实现；结构清晰，支持增量与版本比较 |
| 学术论文 | PubMed E-utilities | 官方 API | PMID、标题、摘要、日期、MeSH |
| 开放全文 | PubMed Central | 官方 API | 仅处理许可允许的全文 |
| 论文补充 | Crossref / Europe PMC | 官方 API | DOI、在线发表时间、引用 |
| 公司动态 | 公司 IR / 新闻稿 / RSS | RSS > 稳定页面 | 临床结果、合作、融资的重要来源 |
| 融资与交易 | SEC EDGAR / 交易所公告 / 公司公告 | 官方 API/页面 | 官方来源优先 |
| 大会 | EULAR / ACR / AAD / EAACI 等 | **各大会单独适配器** | 结构不统一、可能需登录、PDF/动态页面多 |
| 监管 | FDA / EMA / NMPA·CDE | 后续加入 | MVP 不做 |

- ClinicalTrials.gov API v2：https://clinicaltrials.gov/data-api/api
- NCBI E-utilities：https://www.ncbi.nlm.nih.gov/books/NBK25497/

**大会是最难自动化的部分**：不做通用爬虫，一个大会一个「大会适配器」，逐个开发与维护。

## 2. 证据等级（evidence_level，SSOT）

用于 `confidence_score` 与「关键结论是否可发布」：

| 等级 | 来源类型 | 示例 |
| --- | --- | --- |
| A 一手结构化 | 官方注册库 / 监管数据库 | ClinicalTrials.gov、FDA、EMA |
| B 一手同行评议 | 期刊论文 / PMC 全文 | PubMed 收录、有 DOI |
| C 一手机构披露 | 公司稿 / SEC / 交易所 | 公司 IR、8-K |
| D 会议摘要 | 大会摘要 / 壁报 | EULAR/ACR abstract |
| E 二手 | 媒体报道 / 预印本 | 需交叉验证，不单独作结论 |

**规则**：关键结论至少 1 条 A/B/C 级来源；仅 E 级不得作结论（可列「待核」）。

## 3. 适配器统一接口

```python
class SourceAdapter(Protocol):
    source_name: str
    evidence_level: str
    def fetch(self, since: datetime | None) -> list[SourceDocument]: ...
```

每个适配器职责：拉取 → 存原始 JSON/HTML 快照到 `data/raw/<source>/` → 产出 `SourceDocument`（含 URL、published_at、fetched_at、content_hash）。**不在适配器里做实体解析/评分**（那是 processor 的事）。

## 4. 采集礼貌与合规

- 遵守 `HTTP_MAX_RPS`、带 `User-Agent`（见 `.env.example`）、尊重 robots。
- PubMed 建议配置 `NCBI_API_KEY` 提升配额。
- 付费墙全文不抓；PMC 只取许可允许的全文。
- Playwright 仅当无 API/RSS 时启用，且限定到具体适配器。

## 5. `config/sources/*.yaml` 结构（示例）

```yaml
source_id: clinicaltrials
source_name: ClinicalTrials.gov
kind: api                 # api | rss | scrape | browser
evidence_level: A
base_url: https://clinicaltrials.gov/api/v2
enabled: true
rate_limit_rps: 3
notes: 支持增量与版本快照比较
```
