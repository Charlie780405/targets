"""公司 IR / 新闻稿 RSS 采集。"""

from __future__ import annotations

import calendar
import json
import os
import time
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Any, Self

import feedparser  # type: ignore[import-untyped]
import httpx
import yaml  # type: ignore[import-untyped]

from packages.domain.content_hash import compute_content_hash
from packages.source_adapters.base import FetchedDocument

_ROOT = Path(__file__).resolve().parents[3]
_DEFAULT_CONFIG = _ROOT / "config" / "sources" / "companies.yaml"
_DEFAULT_RAW_DIR = _ROOT / "data" / "raw" / "company_ir"


def load_companies_config(path: Path | None = None) -> dict[str, Any]:
    config_path = path or _DEFAULT_CONFIG
    raw = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    return raw if isinstance(raw, dict) else {}


def _parse_rss_datetime(entry: feedparser.FeedParserDict) -> datetime | None:
    if entry.get("published_parsed"):
        return datetime.fromtimestamp(calendar.timegm(entry.published_parsed), tz=UTC)
    if entry.get("updated_parsed"):
        return datetime.fromtimestamp(calendar.timegm(entry.updated_parsed), tz=UTC)
    published = entry.get("published") or entry.get("updated")
    if published:
        try:
            return parsedate_to_datetime(published)
        except (TypeError, ValueError):
            return None
    return None


class CompanyIRAdapter:
    source_id = "companies"

    def __init__(
        self,
        config: dict[str, Any] | None = None,
        *,
        client: httpx.Client | None = None,
        raw_dir: Path | None = None,
        user_agent: str | None = None,
    ) -> None:
        self._config = config or load_companies_config()
        self._source_name = str(self._config.get("source_name", "Company IR"))
        self._evidence_level = str(self._config.get("evidence_level", "C"))
        self._rate_limit_rps = float(self._config.get("rate_limit_rps", 2))
        self._raw_dir = raw_dir or _DEFAULT_RAW_DIR
        self._user_agent = user_agent or os.getenv(
            "HTTP_USER_AGENT", "target-intelligence/0.1 (+https://targets.qyunsgen.com)"
        )
        self._client = client or httpx.Client(
            headers={"User-Agent": str(self._user_agent)},
            timeout=30.0,
        )
        self._owns_client = client is None

    @property
    def source_name(self) -> str:
        return self._source_name

    @property
    def evidence_level(self) -> str:
        return self._evidence_level

    def close(self) -> None:
        if self._owns_client:
            self._client.close()

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *args: object) -> None:
        self.close()

    def _throttle(self) -> None:
        if self._rate_limit_rps > 0:
            time.sleep(1.0 / self._rate_limit_rps)

    def _save_raw(self, org_id: str, payload: dict[str, Any]) -> Path:
        ts = datetime.now(tz=UTC).strftime("%Y%m%dT%H%M%SZ")
        dest_dir = self._raw_dir / org_id
        dest_dir.mkdir(parents=True, exist_ok=True)
        dest = dest_dir / f"{ts}.json"
        dest.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        return dest

    def fetch_rss_url(self, rss_url: str, org_id: str) -> list[FetchedDocument]:
        self._throttle()
        response = self._client.get(rss_url)
        response.raise_for_status()
        return self._parse_feed(response.text, org_id, rss_url=rss_url)

    def _parse_feed(
        self,
        feed_text: str,
        org_id: str,
        *,
        rss_url: str | None = None,
    ) -> list[FetchedDocument]:
        parsed = feedparser.parse(feed_text)
        documents: list[FetchedDocument] = []
        for entry in parsed.entries:
            title = str(entry.get("title") or "Untitled")
            link = str(entry.get("link") or rss_url or "")
            summary = str(entry.get("summary") or entry.get("description") or "")
            published_at = _parse_rss_datetime(entry)
            payload = {
                "org_id": org_id,
                "title": title,
                "summary": summary,
                "link": link,
                "published": published_at.isoformat() if published_at else None,
                "evidence_level": self._evidence_level,
            }
            self._save_raw(org_id, payload)
            content_hash = compute_content_hash(payload)
            external_id = compute_content_hash({"link": link, "title": title})[:16]
            documents.append(
                FetchedDocument(
                    external_id=external_id,
                    source_id=self.source_id,
                    source_name=self._source_name,
                    source_url=link,
                    title=title,
                    published_at=published_at,
                    content_hash=content_hash,
                    payload=payload,
                )
            )
        return documents

    def fetch_rss_xml(self, feed_xml: str, org_id: str) -> list[FetchedDocument]:
        """测试/离线用：直接解析 RSS XML 字符串。"""
        return self._parse_feed(feed_xml, org_id, rss_url="fixture://rss")

    def fetch(self, since: datetime | None = None) -> list[FetchedDocument]:
        del since
        documents: list[FetchedDocument] = []
        for company in self._config.get("companies", []):
            org_id = company["org_id"]
            rss_url = company.get("rss_url")
            if rss_url:
                documents.extend(self.fetch_rss_url(str(rss_url), org_id))
        return documents
