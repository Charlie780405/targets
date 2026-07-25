"""Publication 事件导出上下文 — 从 Event/Evidence 解析文献字段。"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from packages.domain.enums import EventType
from packages.domain.models import Event, Evidence, Publication, SourceDocument

_STUDY_TYPE_RE = re.compile(r"study_type=([^;]+)")
_TARGETS_RE = re.compile(r"targets=([^;]+)")


@dataclass(frozen=True)
class PublicationExportContext:
    pmid: str | None = None
    doi: str | None = None
    abstract: str | None = None
    published_at: str | None = None
    study_type: str | None = None
    matched_targets: tuple[str, ...] = ()
    retracted: bool = False
    analysis_zh: str | None = None
    journal: str | None = None

    @property
    def pubmed_url(self) -> str | None:
        if self.pmid:
            return f"https://pubmed.ncbi.nlm.nih.gov/{self.pmid}/"
        return None

    @property
    def doi_url(self) -> str | None:
        if self.doi:
            return f"https://doi.org/{self.doi}"
        return None


def _parse_summary_fields(summary: str | None) -> tuple[str | None, tuple[str, ...]]:
    if not summary:
        return None, ()
    study_match = _STUDY_TYPE_RE.search(summary)
    study_type = study_match.group(1).strip() if study_match else None
    targets_match = _TARGETS_RE.search(summary)
    targets: tuple[str, ...] = ()
    if targets_match:
        targets = tuple(t.strip() for t in targets_match.group(1).split(",") if t.strip())
    return study_type, targets


def _analysis_from_payload(payload: dict[str, Any] | None) -> str | None:
    if not payload:
        return None
    analysis = payload.get("analysis")
    if isinstance(analysis, dict):
        text = analysis.get("summary_zh") or analysis.get("text")
        return str(text) if text else None
    if isinstance(analysis, str):
        return analysis
    return None


def _journal_from_payload(payload: dict[str, Any] | None) -> str | None:
    if not payload:
        return None
    for key in ("journal", "Journal", "journal_title"):
        value = payload.get(key)
        if value:
            return str(value)
    return None


def resolve_publication_export_context(
    session: Session,
    event: Event,
    evidences: list[Evidence],
) -> PublicationExportContext | None:
    if event.event_type != EventType.PUBLICATION:
        return None

    study_type, matched_targets = _parse_summary_fields(event.summary)
    publication: Publication | None = None
    payload: dict[str, Any] | None = None

    for evidence in evidences:
        if evidence.id.startswith("EVD-PM-"):
            pub_id = evidence.id.removeprefix("EVD-PM-")
            publication = session.get(Publication, pub_id)
            if publication:
                break
        if evidence.source_document_id:
            sdoc = session.get(SourceDocument, evidence.source_document_id)
            if sdoc and isinstance(sdoc.payload_json, dict):
                payload = sdoc.payload_json
                pmid = payload.get("pmid")
                if pmid:
                    publication = session.scalar(
                        select(Publication).where(Publication.pmid == str(pmid))
                    )
                    if publication:
                        break

    if publication is None and evidences:
        publication = session.scalar(
            select(Publication).where(Publication.title == event.title).limit(1)
        )

    if publication and payload is None:
        sdoc_id = f"SDOC-PM-{publication.id}"
        sdoc = session.get(SourceDocument, sdoc_id)
        if sdoc and isinstance(sdoc.payload_json, dict):
            payload = sdoc.payload_json

    if publication is None:
        return PublicationExportContext(
            study_type=study_type,
            matched_targets=matched_targets,
            analysis_zh=_analysis_from_payload(payload),
        )

    published = publication.published_at.isoformat() if publication.published_at else None
    return PublicationExportContext(
        pmid=publication.pmid,
        doi=publication.doi,
        abstract=publication.abstract,
        published_at=published,
        study_type=study_type,
        matched_targets=matched_targets,
        retracted=bool(publication.retracted),
        analysis_zh=_analysis_from_payload(payload),
        journal=_journal_from_payload(payload),
    )
