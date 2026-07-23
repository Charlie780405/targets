"""出版物去重 — DOI 优先，退化 PMID + 标题归一。"""

from __future__ import annotations

import re
from dataclasses import dataclass


def normalize_title(title: str) -> str:
    cleaned = re.sub(r"[^\w\s]", " ", title.lower())
    return re.sub(r"\s+", " ", cleaned).strip()


def normalize_doi(doi: str | None) -> str | None:
    if not doi:
        return None
    value = doi.strip().lower()
    return value.removeprefix("https://doi.org/").removeprefix("doi:")


@dataclass(frozen=True)
class PublicationIdentity:
    doi: str | None
    pmid: str | None
    title: str

    def dedup_key(self) -> str:
        norm_doi = normalize_doi(self.doi)
        if norm_doi:
            return f"doi:{norm_doi}"
        if self.pmid:
            return f"pmid:{self.pmid}"
        return f"title:{normalize_title(self.title)}"


def merge_publication_records(
    existing: dict[str, object],
    incoming: dict[str, object],
) -> dict[str, object]:
    """合并 PubMed 与 Crossref 记录，DOI 与 published_at 互补。"""
    merged = dict(existing)
    for key, value in incoming.items():
        if value is None:
            continue
        if key not in merged or merged[key] in (None, ""):
            merged[key] = value
    # DOI 以 incoming 优先（Crossref 更权威）
    incoming_doi = normalize_doi(str(incoming.get("doi") or "") or None)
    if incoming_doi:
        merged["doi"] = incoming_doi
    return merged


def is_same_publication(a: PublicationIdentity, b: PublicationIdentity) -> bool:
    return a.dedup_key() == b.dedup_key()
