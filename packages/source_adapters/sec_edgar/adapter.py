"""SEC EDGAR 公告采集（8-K 等）。"""

from __future__ import annotations

import json
import os
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Self

import httpx
import yaml  # type: ignore[import-untyped]

from packages.domain.content_hash import compute_content_hash
from packages.entity_resolution.org_normalizer import OrganizationNormalizer
from packages.source_adapters.base import FetchedDocument

_ROOT = Path(__file__).resolve().parents[3]
_DEFAULT_CONFIG = _ROOT / "config" / "sources" / "sec_edgar.yaml"
_DEFAULT_RAW_DIR = _ROOT / "data" / "raw" / "sec_edgar"
_SEC_SUBMISSIONS = "https://data.sec.gov/submissions/CIK{cik}.json"


def load_sec_config(path: Path | None = None) -> dict[str, Any]:
    config_path = path or _DEFAULT_CONFIG
    if not config_path.exists():
        return {"source_id": "sec_edgar", "source_name": "SEC EDGAR", "evidence_level": "C", "forms": ["8-K"]}
    raw = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    return raw if isinstance(raw, dict) else {}


class SecEdgarAdapter:
    source_id = "sec_edgar"

    def __init__(
        self,
        config: dict[str, Any] | None = None,
        *,
        client: httpx.Client | None = None,
        raw_dir: Path | None = None,
        org_normalizer: OrganizationNormalizer | None = None,
    ) -> None:
        self._config = config or load_sec_config()
        self._source_name = str(self._config.get("source_name", "SEC EDGAR"))
        self._evidence_level = str(self._config.get("evidence_level", "C"))
        self._forms = set(self._config.get("forms", ["8-K"]))
        self._rate_limit_rps = float(self._config.get("rate_limit_rps", 2))
        self._raw_dir = raw_dir or _DEFAULT_RAW_DIR
        self._orgs = org_normalizer or OrganizationNormalizer.from_seed()
        user_agent = os.getenv(
            "HTTP_USER_AGENT", "target-intelligence/0.1 (+mailto:Charlie780405@outlook.com)"
        )
        self._client = client or httpx.Client(
            headers={"User-Agent": user_agent, "Accept": "application/json"},
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

    def fetch_submissions(self, cik: str) -> dict[str, Any]:
        self._throttle()
        response = self._client.get(_SEC_SUBMISSIONS.format(cik=cik.zfill(10)))
        response.raise_for_status()
        data = response.json()
        return data if isinstance(data, dict) else {}

    def fetch_filings_for_org(self, org_id: str, cik: str, *, limit: int = 20) -> list[FetchedDocument]:
        data = self.fetch_submissions(cik)
        recent = data.get("filings", {}).get("recent") or {}
        forms = recent.get("form") or []
        dates = recent.get("filingDate") or []
        accessions = recent.get("accessionNumber") or []
        primary_docs = recent.get("primaryDocument") or []

        documents: list[FetchedDocument] = []
        count = 0
        for idx, form in enumerate(forms):
            if form not in self._forms:
                continue
            accession = accessions[idx] if idx < len(accessions) else ""
            filing_date = dates[idx] if idx < len(dates) else None
            primary = primary_docs[idx] if idx < len(primary_docs) else ""
            accession_no_dash = accession.replace("-", "")
            url = (
                f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/"
                f"{accession_no_dash}/{primary}"
            )
            title = f"{form} filing by {org_id} ({filing_date})"
            payload = {
                "org_id": org_id,
                "cik": cik,
                "form": form,
                "filing_date": filing_date,
                "accession": accession,
                "url": url,
                "evidence_level": self._evidence_level,
            }
            dest_dir = self._raw_dir / org_id
            dest_dir.mkdir(parents=True, exist_ok=True)
            (dest_dir / f"{accession}.json").write_text(
                json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
            )
            content_hash = compute_content_hash(payload)
            documents.append(
                FetchedDocument(
                    external_id=accession,
                    source_id=self.source_id,
                    source_name=self._source_name,
                    source_url=url,
                    title=title,
                    published_at=(
                        datetime.strptime(filing_date, "%Y-%m-%d").replace(tzinfo=UTC)
                        if filing_date
                        else None
                    ),
                    content_hash=content_hash,
                    payload=payload,
                )
            )
            count += 1
            if count >= limit:
                break
        return documents

    def fetch(self, since: datetime | None = None) -> list[FetchedDocument]:
        del since
        documents: list[FetchedDocument] = []
        for org in self._orgs.all_with_sec_cik():
            if org.sec_cik:
                documents.extend(self.fetch_filings_for_org(org.org_id, org.sec_cik))
        return documents
