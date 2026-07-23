"""PubMed E-utilities 采集适配器。"""

from __future__ import annotations

import os
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Self
from urllib.parse import urlencode

import httpx
import yaml  # type: ignore[import-untyped]

from packages.source_adapters.base import FetchedDocument
from packages.source_adapters.pubmed.parser import parse_pubmed_article
from packages.source_adapters.pubmed.query_builder import build_pubmed_query

_ROOT = Path(__file__).resolve().parents[3]
_DEFAULT_CONFIG = _ROOT / "config" / "sources" / "pubmed.yaml"
_DEFAULT_RAW_DIR = _ROOT / "data" / "raw" / "pubmed"
_EUTILS_BASE = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"


def load_pubmed_config(path: Path | None = None) -> dict[str, Any]:
    config_path = path or _DEFAULT_CONFIG
    raw = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    return raw if isinstance(raw, dict) else {}


class PubMedAdapter:
    source_id = "pubmed"

    def __init__(
        self,
        config: dict[str, Any] | None = None,
        *,
        client: httpx.Client | None = None,
        raw_dir: Path | None = None,
    ) -> None:
        self._config = config or load_pubmed_config()
        self._source_name = str(self._config.get("source_name", "PubMed"))
        self._rate_limit_rps = float(self._config.get("rate_limit_rps", 3))
        self._raw_dir = raw_dir or _DEFAULT_RAW_DIR
        self._api_key = os.getenv("NCBI_API_KEY")
        self._tool = os.getenv("NCBI_TOOL", "target-intelligence")
        self._email = os.getenv("NCBI_EMAIL", "dev@example.com")
        self._client = client or httpx.Client(timeout=30.0)
        self._owns_client = client is None

    @property
    def source_name(self) -> str:
        return self._source_name

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

    def _base_params(self) -> dict[str, str]:
        params = {"tool": self._tool, "email": self._email}
        if self._api_key:
            params["api_key"] = self._api_key
        return params

    def esearch(self, term: str, *, retmax: int = 100) -> list[str]:
        params = {
            **self._base_params(),
            "db": "pubmed",
            "term": term,
            "retmode": "json",
            "retmax": str(retmax),
        }
        self._throttle()
        response = self._client.get(f"{_EUTILS_BASE}/esearch.fcgi", params=params)
        response.raise_for_status()
        data = response.json()
        idlist = data.get("esearchresult", {}).get("idlist") or []
        return [str(i) for i in idlist]

    def efetch_xml(self, pmids: list[str]) -> str:
        if not pmids:
            return ""
        params = {
            **self._base_params(),
            "db": "pubmed",
            "id": ",".join(pmids),
            "retmode": "xml",
        }
        self._throttle()
        response = self._client.get(f"{_EUTILS_BASE}/efetch.fcgi", params=params)
        response.raise_for_status()
        return response.text

    def _save_raw(self, pmid: str, xml_text: str) -> Path:
        ts = datetime.now(tz=UTC).strftime("%Y%m%dT%H%M%SZ")
        dest_dir = self._raw_dir / pmid
        dest_dir.mkdir(parents=True, exist_ok=True)
        dest = dest_dir / f"{ts}.xml"
        dest.write_text(xml_text, encoding="utf-8")
        return dest

    def _split_articles(self, xml_text: str) -> list[str]:
        """按 PubmedArticle 切分批量 efetch XML。"""
        if not xml_text.strip():
            return []
        parts = xml_text.split("<PubmedArticle>")
        articles: list[str] = []
        for chunk in parts[1:]:
            articles.append(f"<PubmedArticle>{chunk.split('</PubmedArticle>')[0]}</PubmedArticle>")
        if articles:
            return articles
        return [xml_text]

    def fetch(self, since: datetime | None = None) -> list[FetchedDocument]:
        del since
        term = build_pubmed_query()
        pmids = self.esearch(term, retmax=100)
        if not pmids:
            return []

        xml_batch = self.efetch_xml(pmids)
        documents: list[FetchedDocument] = []
        for article_xml in self._split_articles(xml_batch):
            parsed = parse_pubmed_article(article_xml)
            pmid = parsed["pmid"]
            self._save_raw(pmid, article_xml)
            url = f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/"
            documents.append(
                FetchedDocument(
                    external_id=pmid,
                    source_id=self.source_id,
                    source_name=self._source_name,
                    source_url=url,
                    title=parsed["title"],
                    published_at=(
                        datetime.combine(parsed["published_at"], datetime.min.time(), tzinfo=UTC)
                        if parsed.get("published_at")
                        else None
                    ),
                    content_hash=parsed["content_hash"],
                    payload={**parsed, "raw_xml": article_xml},
                )
            )
        return documents

    def build_esearch_url(self, term: str, *, retmax: int = 100) -> str:
        params = {**self._base_params(), "db": "pubmed", "term": term, "retmode": "json", "retmax": retmax}
        return f"{_EUTILS_BASE}/esearch.fcgi?{urlencode(params)}"
