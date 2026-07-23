"""PubMed 采集入口。"""

from __future__ import annotations

import argparse
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from apps.processor.publication_extract import extract_publication_fields
from packages.domain.database import SessionLocal, create_db_engine
from packages.domain.enums import EventType, EvidenceLevel, MedicalReviewStatus
from packages.domain.models import Event, Evidence, Publication, SourceDocument
from packages.entity_resolution.dedup import (
    PublicationIdentity,
    merge_publication_records,
    normalize_doi,
)
from packages.source_adapters.base import FetchedDocument
from packages.source_adapters.crossref.adapter import CrossrefAdapter
from packages.source_adapters.pubmed.adapter import PubMedAdapter


def _next_event_id(session: Session, year: int) -> str:
    prefix = f"EVT-{year}-"
    rows = session.scalars(select(Event.id).where(Event.id.like(f"{prefix}%"))).all()
    max_seq = max((int(str(eid).split("-")[-1]) for eid in rows if str(eid).split("-")[-1].isdigit()), default=0)
    return f"{prefix}{max_seq + 1:05d}"


def _find_existing_publication(session: Session, identity: PublicationIdentity) -> Publication | None:
    norm_doi = normalize_doi(identity.doi)
    if norm_doi:
        found = session.scalar(select(Publication).where(Publication.doi == norm_doi))
        if found:
            return found
    if identity.pmid:
        found = session.scalar(select(Publication).where(Publication.pmid == identity.pmid))
        if found:
            return found
    return None


def persist_publication(
    session: Session,
    doc: FetchedDocument,
    *,
    crossref: CrossrefAdapter | None = None,
) -> tuple[Publication, Event | None]:
    payload = dict(doc.payload)
    if crossref and payload.get("doi"):
        payload = crossref.enrich_publication(payload)

    identity = PublicationIdentity(
        doi=payload.get("doi"),
        pmid=payload.get("pmid"),
        title=str(payload.get("title") or doc.title or ""),
    )
    existing = _find_existing_publication(session, identity)

    pub_fields = {
        "id": payload.get("id") or f"PMID-{identity.pmid}",
        "pmid": payload.get("pmid"),
        "doi": payload.get("doi"),
        "title": payload.get("title") or doc.title,
        "abstract": payload.get("abstract"),
        "published_at": payload.get("published_at"),
        "retracted": bool(payload.get("retracted")),
        "content_hash": doc.content_hash,
    }

    if existing:
        merged = merge_publication_records(
            {
                "pmid": existing.pmid,
                "doi": existing.doi,
                "title": existing.title,
                "abstract": existing.abstract,
                "published_at": existing.published_at,
                "retracted": existing.retracted,
            },
            pub_fields,
        )
        for key, value in merged.items():
            if key != "id" and hasattr(existing, key):
                setattr(existing, key, value)
        publication = existing
        is_new = False
    else:
        publication = Publication(**pub_fields)
        session.add(publication)
        is_new = True

    session.flush()

    source_doc = SourceDocument(
        id=f"SDOC-PM-{publication.id}",
        source_id=doc.source_id,
        source_name=doc.source_name,
        source_url=doc.source_url,
        title=doc.title,
        published_at=doc.published_at,
        fetched_at=datetime.now(tz=UTC),
        content_hash=doc.content_hash,
        payload_json={k: v for k, v in payload.items() if k != "raw_xml"},
    )
    session.merge(source_doc)

    event: Event | None = None
    if is_new:
        extracted = extract_publication_fields(payload)
        summary_parts = [f"study_type={extracted['study_type']}"]
        if extracted["matched_targets"]:
            summary_parts.append(f"targets={','.join(extracted['matched_targets'])}")
        if extracted["retracted"]:
            summary_parts.append("RETRACTED")

        event = Event(
            id=_next_event_id(session, datetime.now(tz=UTC).year),
            event_type=EventType.PUBLICATION,
            event_date=publication.published_at or datetime.now(tz=UTC).date(),
            discovered_at=datetime.now(tz=UTC),
            title=publication.title,
            summary="; ".join(summary_parts),
            medical_review_status=MedicalReviewStatus.PENDING,
            source_count=1,
            content_hash=doc.content_hash,
        )
        session.add(event)
        session.flush()
        session.add(
            Evidence(
                id=f"EVD-PM-{publication.id}",
                event_id=event.id,
                source_document_id=source_doc.id,
                source_name=doc.source_name,
                source_url=doc.source_url,
                evidence_snippet=(publication.abstract or "")[:500] or None,
                evidence_level=EvidenceLevel.B,
                content_hash=doc.content_hash,
            )
        )
    elif publication.retracted:
        # 已有记录标记撤稿时也生成事件
        event = Event(
            id=_next_event_id(session, datetime.now(tz=UTC).year),
            event_type=EventType.PUBLICATION,
            event_date=publication.published_at or datetime.now(tz=UTC).date(),
            discovered_at=datetime.now(tz=UTC),
            title=f"[Retracted] {publication.title}",
            summary="publication marked retracted",
            medical_review_status=MedicalReviewStatus.PENDING,
            source_count=1,
            content_hash=doc.content_hash,
        )
        session.add(event)

    return publication, event


def run_collect(*, dry_run: bool = False) -> dict[str, int]:
    stats = {"fetched": 0, "publications": 0, "events": 0, "merged": 0}
    with PubMedAdapter() as pubmed, CrossrefAdapter() as crossref:
        documents = pubmed.fetch()

    stats["fetched"] = len(documents)
    if dry_run:
        return stats

    session = SessionLocal()
    try:
        for doc in documents:
            existing_before = session.scalar(
                select(Publication).where(Publication.pmid == doc.external_id)
            )
            _publication, event = persist_publication(session, doc, crossref=crossref)
            stats["publications"] += 1
            if existing_before:
                stats["merged"] += 1
            if event:
                stats["events"] += 1
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
    return stats


def main() -> None:
    parser = argparse.ArgumentParser(description="Collect PubMed publications")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--init-db", action="store_true")
    args = parser.parse_args()

    if args.init_db:
        from packages.domain.database import Base

        Base.metadata.create_all(create_db_engine())

    stats = run_collect(dry_run=args.dry_run)
    print(
        f"pubmed collect: fetched={stats['fetched']} publications={stats['publications']} "
        f"events={stats['events']} merged={stats['merged']}"
    )


if __name__ == "__main__":
    main()
