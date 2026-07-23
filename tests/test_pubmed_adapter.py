"""PubMed 适配器与解析测试。"""

from __future__ import annotations

import json
from pathlib import Path

import httpx

from packages.source_adapters.crossref.adapter import CrossrefAdapter
from packages.source_adapters.pubmed.adapter import PubMedAdapter
from packages.source_adapters.pubmed.parser import parse_pubmed_article
from packages.source_adapters.pubmed.query_builder import build_pubmed_query

_FIXTURES = Path(__file__).resolve().parent / "fixtures"


def test_build_pubmed_query_contains_target_and_indication() -> None:
    query = build_pubmed_query()
    assert "IL-4R" in query or "IL4R" in query
    assert "atopic dermatitis" in query.lower() or "Atopic Dermatitis" in query
    assert " AND " in query


def test_parse_normal_article() -> None:
    xml_text = (_FIXTURES / "pubmed" / "article_normal.xml").read_text(encoding="utf-8")
    parsed = parse_pubmed_article(xml_text)
    assert parsed["pmid"] == "12345678"
    assert parsed["doi"] == "10.1000/test.ad.001"
    assert parsed["retracted"] is False
    assert "EASI" in (parsed["abstract"] or "")


def test_parse_retracted_article() -> None:
    xml_text = (_FIXTURES / "pubmed" / "article_retracted.xml").read_text(encoding="utf-8")
    parsed = parse_pubmed_article(xml_text)
    assert parsed["pmid"] == "87654321"
    assert parsed["retracted"] is True


def test_pubmed_adapter_esearch_efetch_mock(tmp_path: Path) -> None:
    esearch = json.loads((_FIXTURES / "pubmed" / "esearch_response.json").read_text())
    article_xml = (_FIXTURES / "pubmed" / "article_normal.xml").read_text(encoding="utf-8")

    def handler(request: httpx.Request) -> httpx.Response:
        if "esearch.fcgi" in str(request.url):
            return httpx.Response(200, json=esearch)
        if "efetch.fcgi" in str(request.url):
            return httpx.Response(200, text=article_xml)
        return httpx.Response(404)

    transport = httpx.MockTransport(handler)
    client = httpx.Client(transport=transport)
    adapter = PubMedAdapter(client=client, raw_dir=tmp_path / "raw")
    try:
        docs = adapter.fetch()
        assert len(docs) == 1
        assert docs[0].external_id == "12345678"
        assert docs[0].source_id == "pubmed"
    finally:
        adapter.close()


def test_crossref_enrich_publication() -> None:
    crossref_json = json.loads((_FIXTURES / "crossref" / "work_response.json").read_text())

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=crossref_json)

    transport = httpx.MockTransport(handler)
    client = httpx.Client(transport=transport)
    adapter = CrossrefAdapter(client=client)
    try:
        record = {"doi": "10.1000/test.ad.001", "title": "Local title", "published_at": None}
        enriched = adapter.enrich_publication(record)
        assert enriched["crossref"]["publisher"] == "Example Press"
        assert enriched["published_at"] is not None
    finally:
        adapter.close()
