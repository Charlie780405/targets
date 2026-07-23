"""公司 IR 与 SEC 适配器测试。"""

from __future__ import annotations

import json
from pathlib import Path

import httpx

from apps.processor.company_event_classifier import classify_company_release
from packages.domain.enums import EventType
from packages.entity_resolution.org_normalizer import OrganizationNormalizer
from packages.source_adapters.company_ir.adapter import CompanyIRAdapter
from packages.source_adapters.sec_edgar.adapter import SecEdgarAdapter

_FIXTURES = Path(__file__).resolve().parent / "fixtures"


def test_company_ir_parse_fixture_rss(tmp_path: Path) -> None:
    rss = (_FIXTURES / "company_ir" / "regeneron_rss.xml").read_text(encoding="utf-8")
    adapter = CompanyIRAdapter(raw_dir=tmp_path / "raw")
    docs = adapter.fetch_rss_xml(rss, "regeneron")
    assert len(docs) == 2
    assert docs[0].payload["evidence_level"] == "C"
    assert classify_company_release(docs[0].title, docs[0].payload.get("summary")) == EventType.CLINICAL_RESULT
    assert classify_company_release(docs[1].title, docs[1].payload.get("summary")) == EventType.DEAL


def test_sec_edgar_mock_submissions(tmp_path: Path) -> None:
    payload = json.loads((_FIXTURES / "sec_edgar" / "regeneron_submissions.json").read_text())

    def handler(request: httpx.Request) -> httpx.Response:
        if "submissions/CIK" in str(request.url):
            return httpx.Response(200, json=payload)
        return httpx.Response(404)

    transport = httpx.MockTransport(handler)
    client = httpx.Client(transport=transport)
    orgs = OrganizationNormalizer.from_seed()
    adapter = SecEdgarAdapter(client=client, raw_dir=tmp_path / "sec", org_normalizer=orgs)
    try:
        docs = adapter.fetch_filings_for_org("regeneron", "872589", limit=5)
        assert len(docs) == 2  # two 8-K in fixture
        assert docs[0].source_id == "sec_edgar"
        assert docs[0].payload["form"] == "8-K"
    finally:
        adapter.close()
