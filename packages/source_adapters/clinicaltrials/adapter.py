"""ClinicalTrials.gov API v2 采集适配器。"""

from __future__ import annotations

import json
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Self

import httpx
import yaml  # type: ignore[import-untyped]

from packages.domain.content_hash import compute_content_hash
from packages.source_adapters.base import FetchedDocument
from packages.source_adapters.clinicaltrials.parser import build_study_url, get_nct_id

_ROOT = Path(__file__).resolve().parents[3]
_DEFAULT_CONFIG = _ROOT / "config" / "sources" / "clinicaltrials.yaml"
_DEFAULT_TARGETS_DIR = _ROOT / "config" / "targets"
_DEFAULT_RAW_DIR = _ROOT / "data" / "raw" / "clinicaltrials"


def load_source_config(path: Path | None = None) -> dict[str, Any]:
    config_path = path or _DEFAULT_CONFIG
    raw = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    return raw if isinstance(raw, dict) else {}


def build_query_term(targets_dir: Path | None = None) -> str:
    """从靶点种子别名构建 query.term（OR 连接）。"""
    directory = targets_dir or _DEFAULT_TARGETS_DIR
    terms: list[str] = []
    for path in sorted(directory.glob("*.yaml")):
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        if not data:
            continue
        terms.append(data["canonical_name"])
        terms.extend(data.get("aliases", []))
        if data.get("gene"):
            terms.append(data["gene"])
    # 去重保序
    seen: set[str] = set()
    unique: list[str] = []
    for term in terms:
        key = term.lower()
        if key not in seen:
            seen.add(key)
            unique.append(term)
    return " OR ".join(unique)


class ClinicalTrialsAdapter:
    source_id = "clinicaltrials"

    def __init__(
        self,
        config: dict[str, Any] | None = None,
        *,
        client: httpx.Client | None = None,
        raw_dir: Path | None = None,
        user_agent: str = "target-intelligence/0.1",
    ) -> None:
        self._config = config or load_source_config()
        self._base_url = str(self._config.get("base_url", "https://clinicaltrials.gov/api/v2"))
        self._source_name = str(self._config.get("source_name", "ClinicalTrials.gov"))
        self._rate_limit_rps = float(self._config.get("rate_limit_rps", 3))
        self._raw_dir = raw_dir or _DEFAULT_RAW_DIR
        self._client = client or httpx.Client(
            headers={"User-Agent": user_agent},
            timeout=30.0,
        )
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

    def _save_raw_snapshot(self, nct_id: str, payload: dict[str, Any]) -> Path:
        ts = datetime.now(tz=UTC).strftime("%Y%m%dT%H%M%SZ")
        dest_dir = self._raw_dir / nct_id
        dest_dir.mkdir(parents=True, exist_ok=True)
        dest = dest_dir / f"{ts}.json"
        dest.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        return dest

    def fetch_page(
        self,
        query_term: str,
        *,
        page_token: str | None = None,
        page_size: int = 100,
    ) -> dict[str, Any]:
        params: dict[str, str | int] = {
            "query.term": query_term,
            "pageSize": page_size,
            "format": "json",
        }
        if page_token:
            params["pageToken"] = page_token
        self._throttle()
        response = self._client.get(f"{self._base_url}/studies", params=params)
        response.raise_for_status()
        data = response.json()
        return data if isinstance(data, dict) else {"studies": data}

    def fetch(self, since: datetime | None = None) -> list[FetchedDocument]:
        del since  # MVP：全量分页；后续按 LastUpdatePostDate 增量
        query_term = build_query_term()
        documents: list[FetchedDocument] = []
        page_token: str | None = None

        while True:
            page = self.fetch_page(query_term, page_token=page_token)
            studies = page.get("studies") or []
            for study in studies:
                if not isinstance(study, dict):
                    continue
                nct_id = get_nct_id(study)
                if not nct_id:
                    continue
                self._save_raw_snapshot(nct_id, study)
                content_hash = compute_content_hash(study)
                documents.append(
                    FetchedDocument(
                        external_id=nct_id,
                        source_id=self.source_id,
                        source_name=self._source_name,
                        source_url=build_study_url(nct_id),
                        title=study.get("protocolSection", {})
                        .get("identificationModule", {})
                        .get("briefTitle"),
                        published_at=None,
                        content_hash=content_hash,
                        payload=study,
                    )
                )
            page_token = page.get("nextPageToken")
            if not page_token:
                break

        return documents
