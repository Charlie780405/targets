"""出版物去重测试。"""

from packages.entity_resolution.dedup import (
    PublicationIdentity,
    merge_publication_records,
    normalize_doi,
    normalize_title,
)


def test_dedup_key_doi_priority() -> None:
    a = PublicationIdentity(doi="10.1000/test.ad.001", pmid="123", title="A")
    b = PublicationIdentity(doi="10.1000/test.ad.001", pmid="999", title="B")
    assert a.dedup_key() == b.dedup_key()


def test_dedup_key_pmid_fallback() -> None:
    identity = PublicationIdentity(doi=None, pmid="12345678", title="Some Title")
    assert identity.dedup_key() == "pmid:12345678"


def test_normalize_title() -> None:
    assert normalize_title("  Hello, World! ") == "hello world"


def test_normalize_doi() -> None:
    assert normalize_doi("https://doi.org/10.1000/abc") == "10.1000/abc"


def test_merge_publication_records() -> None:
    existing = {"pmid": "123", "doi": None, "title": "Old", "published_at": None, "retracted": False}
    incoming = {"doi": "10.1000/test.ad.001", "published_at": "2026-06-15", "title": "New Title"}
    merged = merge_publication_records(existing, incoming)
    assert merged["doi"] == "10.1000/test.ad.001"
    assert merged["published_at"] == "2026-06-15"
    assert merged["pmid"] == "123"
