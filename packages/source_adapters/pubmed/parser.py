"""PubMed efetch XML 解析。"""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from datetime import date
from typing import Any

from packages.domain.content_hash import compute_content_hash

RETRACTION_PATTERNS = (
    "retracted publication",
    "retraction of publication",
    "retraction notice",
)


def _local(tag: str) -> str:
    return tag.split("}")[-1] if "}" in tag else tag


def _find_text(parent: ET.Element, name: str) -> str | None:
    for child in parent.iter():
        if _local(child.tag) == name and child.text:
            return child.text.strip()
    return None


def _find_all_text(parent: ET.Element, name: str) -> list[str]:
    return [
        child.text.strip()
        for child in parent.iter()
        if _local(child.tag) == name and child.text and child.text.strip()
    ]


def _parse_pub_date(parent: ET.Element) -> date | None:
    for elem in parent.iter():
        if _local(elem.tag) != "PubDate":
            continue
        year = month = day = None
        for child in elem:
            tag = _local(child.tag)
            if child.text and tag in {"Year", "Month", "Day"}:
                if tag == "Year":
                    year = int(child.text)
                elif tag == "Month":
                    month = _parse_month(child.text)
                elif tag == "Day":
                    day = int(child.text)
        if year and month:
            return date(year, month, day or 1)
    return None


def _parse_month(value: str) -> int:
    mapping = {
        "Jan": 1,
        "Feb": 2,
        "Mar": 3,
        "Apr": 4,
        "May": 5,
        "Jun": 6,
        "Jul": 7,
        "Aug": 8,
        "Sep": 9,
        "Oct": 10,
        "Nov": 11,
        "Dec": 12,
    }
    if value.isdigit():
        return int(value)
    return mapping.get(value[:3], 1)


def _extract_doi(article: ET.Element) -> str | None:
    for elem in article.iter():
        if _local(elem.tag) == "ArticleId" and elem.attrib.get("IdType") == "doi" and elem.text:
            return elem.text.strip()
        if _local(elem.tag) == "ELocationID" and elem.attrib.get("EIdType") == "doi" and elem.text:
            return elem.text.strip()
    return None


def _extract_abstract(article: ET.Element) -> str | None:
    parts: list[str] = []
    for elem in article.iter():
        if _local(elem.tag) == "AbstractText" and elem.text:
            label = elem.attrib.get("Label")
            text = elem.text.strip()
            parts.append(f"{label}: {text}" if label else text)
    if parts:
        return " ".join(parts)
    return _find_text(article, "Abstract")


def is_retracted(article: ET.Element) -> bool:
    pub_types = [t.lower() for t in _find_all_text(article, "PublicationType")]
    for pub_type in pub_types:
        if any(pat in pub_type for pat in RETRACTION_PATTERNS):
            return True
    for elem in article.iter():
        if _local(elem.tag) == "CommentsCorrections":
            ref_type = elem.attrib.get("RefType", "").lower()
            if "retract" in ref_type:
                return True
    return False


def parse_pubmed_article(xml_text: str) -> dict[str, Any]:
    root = ET.fromstring(xml_text)
    article_elem = root.find(".//PubmedArticle")
    article = article_elem if article_elem is not None else root

    pmid = _find_text(article, "PMID")
    if not pmid:
        raise ValueError("PubMed XML missing PMID")

    title = _find_text(article, "ArticleTitle") or "Untitled"
    abstract = _extract_abstract(article)
    doi = _extract_doi(article)
    published_at = _parse_pub_date(article)
    retracted = is_retracted(article)

    record = {
        "id": f"PMID-{pmid}",
        "pmid": pmid,
        "doi": doi,
        "title": title,
        "abstract": abstract,
        "published_at": published_at,
        "retracted": retracted,
    }
    record["content_hash"] = compute_content_hash(
        {"pmid": pmid, "doi": doi, "title": title, "abstract": abstract, "retracted": retracted}
    )
    return record


def infer_study_type(title: str, abstract: str | None) -> str:
    text = f"{title} {abstract or ''}".lower()
    if re.search(r"\brandomized\b|\bclinical trial\b|\bphase [i1234]\b", text):
        return "clinical_trial"
    if re.search(r"\bmeta-analysis\b|\bsystematic review\b", text):
        return "systematic_review"
    if re.search(r"\breview\b", text):
        return "review"
    return "other"
