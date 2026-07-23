"""Crossref 补充 DOI 元数据。"""

from __future__ import annotations

import time
from datetime import date
from typing import Any, Self
from urllib.parse import quote

import httpx

_CROSSREF_BASE = "https://api.crossref.org/works"


class CrossrefAdapter:
    source_id = "crossref"

    def __init__(
        self,
        *,
        client: httpx.Client | None = None,
        rate_limit_rps: float = 3.0,
        user_agent: str = "target-intelligence/0.1 (mailto:dev@example.com)",
    ) -> None:
        self._rate_limit_rps = rate_limit_rps
        self._client = client or httpx.Client(
            headers={"User-Agent": user_agent},
            timeout=30.0,
        )
        self._owns_client = client is None

    @property
    def source_name(self) -> str:
        return "Crossref"

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

    def fetch_work(self, doi: str) -> dict[str, Any]:
        self._throttle()
        encoded = quote(doi, safe="")
        response = self._client.get(f"{_CROSSREF_BASE}/{encoded}")
        response.raise_for_status()
        message = response.json().get("message") or {}
        published = None
        for key in ("published-print", "published-online", "created"):
            parts = (message.get(key) or {}).get("date-parts")
            if parts and parts[0]:
                y = parts[0][0]
                m = parts[0][1] if len(parts[0]) > 1 else 1
                d = parts[0][2] if len(parts[0]) > 2 else 1
                published = date(y, m, d)
                break
        return {
            "doi": message.get("DOI") or doi,
            "title": (message.get("title") or [""])[0],
            "published_at": published,
            "publisher": message.get("publisher"),
            "type": message.get("type"),
            "url": message.get("URL"),
        }

    def enrich_publication(self, record: dict[str, Any]) -> dict[str, Any]:
        doi = record.get("doi")
        if not doi:
            return record
        try:
            crossref = self.fetch_work(doi)
        except httpx.HTTPError:
            return record
        merged = dict(record)
        if crossref.get("published_at") and not merged.get("published_at"):
            merged["published_at"] = crossref["published_at"]
        merged["crossref"] = crossref
        return merged
