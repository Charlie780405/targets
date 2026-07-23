"""ClinicalTrials.gov 适配器测试。"""

from __future__ import annotations

import json
from pathlib import Path

import httpx
import vcr

from packages.source_adapters.clinicaltrials.adapter import (
    ClinicalTrialsAdapter,
    build_query_term,
)
from packages.source_adapters.clinicaltrials.parser import get_nct_id, parse_trial_record

_FIXTURES = Path(__file__).resolve().parent / "fixtures" / "clinicaltrials"
_CASSETTES = Path(__file__).resolve().parent / "cassettes"


def test_build_query_term_includes_il4ra_aliases() -> None:
    term = build_query_term()
    assert "IL-4Rα" in term or "IL4R" in term
    assert " OR " in term


def test_parse_trial_record_from_fixture() -> None:
    study = json.loads((_FIXTURES / "study_v1_recruiting.json").read_text(encoding="utf-8"))
    parsed = parse_trial_record(study)
    assert parsed["nct_id"] == "NCT00000001"
    assert parsed["overall_status"] == "RECRUITING"
    assert parsed["enrollment"] == 100
    assert parsed["watch_fields"]["OverallStatus"] == "RECRUITING"


def test_adapter_fetch_page_with_mock_transport(tmp_path: Path) -> None:
    page = json.loads((_FIXTURES / "studies_page1.json").read_text(encoding="utf-8"))

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=page)

    transport = httpx.MockTransport(handler)
    client = httpx.Client(transport=transport)
    adapter = ClinicalTrialsAdapter(client=client, raw_dir=tmp_path / "raw")
    try:
        result = adapter.fetch_page("IL4R", page_size=100)
        assert len(result["studies"]) == 1
        assert get_nct_id(result["studies"][0]) == "NCT00000001"
    finally:
        adapter.close()


def test_adapter_fetch_vcr_replay(tmp_path: Path) -> None:
    my_vcr = vcr.VCR(
        cassette_library_dir=str(_CASSETTES),
        record_mode="none",
        match_on=["method", "scheme", "host", "port", "path", "query"],
    )
    with my_vcr.use_cassette("clinicaltrials_fetch.yaml"), ClinicalTrialsAdapter(
        raw_dir=tmp_path / "raw"
    ) as adapter:
        # 仅测单页回放，避免分页循环
        page = adapter.fetch_page(build_query_term(), page_size=100)
        assert len(page.get("studies", [])) >= 1
