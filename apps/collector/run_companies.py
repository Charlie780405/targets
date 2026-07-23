"""公司与投融资采集入口。"""

from __future__ import annotations

import argparse
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from apps.processor.company_event_classifier import classify_company_release
from apps.processor.source_reliability import confidence_from_evidence_level
from packages.domain.database import SessionLocal, create_db_engine
from packages.domain.enums import EvidenceLevel, MedicalReviewStatus
from packages.domain.models import Event, Evidence, SourceDocument
from packages.entity_resolution.asset_resolver import AssetResolver
from packages.entity_resolution.org_normalizer import OrganizationNormalizer
from packages.source_adapters.base import FetchedDocument
from packages.source_adapters.company_ir.adapter import CompanyIRAdapter
from packages.source_adapters.sec_edgar.adapter import SecEdgarAdapter


def _next_event_id(session: Session, year: int) -> str:
    prefix = f"EVT-{year}-"
    rows = session.scalars(select(Event.id).where(Event.id.like(f"{prefix}%"))).all()
    max_seq = max((int(str(eid).split("-")[-1]) for eid in rows if str(eid).split("-")[-1].isdigit()), default=0)
    return f"{prefix}{max_seq + 1:05d}"


def persist_company_document(
    session: Session,
    doc: FetchedDocument,
    *,
    asset_resolver: AssetResolver,
    org_normalizer: OrganizationNormalizer,
) -> Event | None:
    payload = dict(doc.payload)
    org_id = payload.get("org_id") or org_normalizer.resolve(doc.title or "")
    evidence_level = str(payload.get("evidence_level", "C"))
    confidence = confidence_from_evidence_level(evidence_level)

    existing = session.scalar(
        select(SourceDocument).where(
            SourceDocument.source_url == doc.source_url,
            SourceDocument.content_hash == doc.content_hash,
        )
    )
    if existing:
        return None

    source_doc = SourceDocument(
        id=f"SDOC-CO-{doc.external_id}",
        source_id=doc.source_id,
        source_name=doc.source_name,
        source_url=doc.source_url,
        title=doc.title,
        published_at=doc.published_at,
        fetched_at=datetime.now(tz=UTC),
        content_hash=doc.content_hash,
        payload_json=payload,
    )
    session.add(source_doc)

    event_type = classify_company_release(doc.title or "", payload.get("summary"))
    if event_type is None:
        return None

    text = f"{doc.title} {payload.get('summary', '')}"
    assets = asset_resolver.resolve_in_text(text)
    asset_hint = assets[0].matched_token if assets else None
    summary_parts = [f"org={org_id}", f"evidence_level={evidence_level}"]
    if asset_hint:
        summary_parts.append(f"asset={asset_hint}")

    event = Event(
        id=_next_event_id(session, datetime.now(tz=UTC).year),
        event_type=event_type,
        organization_id=org_id,
        event_date=(doc.published_at or datetime.now(tz=UTC)).date(),
        discovered_at=datetime.now(tz=UTC),
        title=doc.title or "Company release",
        summary="; ".join(summary_parts),
        confidence_score=confidence,
        medical_review_status=MedicalReviewStatus.PENDING,
        source_count=1,
        content_hash=doc.content_hash,
    )
    session.add(event)
    session.flush()
    session.add(
        Evidence(
            id=f"EVD-CO-{doc.external_id}",
            event_id=event.id,
            source_document_id=source_doc.id,
            source_name=doc.source_name,
            source_url=doc.source_url,
            evidence_snippet=(payload.get("summary") or doc.title or "")[:500],
            evidence_level=EvidenceLevel(evidence_level),
            published_at=doc.published_at,
            content_hash=doc.content_hash,
        )
    )
    return event


def run_collect(*, dry_run: bool = False) -> dict[str, int]:
    stats = {"fetched": 0, "events": 0, "skipped_dup": 0}
    asset_resolver = AssetResolver.from_seed()
    org_normalizer = OrganizationNormalizer.from_seed()

    documents: list[FetchedDocument] = []
    with CompanyIRAdapter() as company_adapter, SecEdgarAdapter(org_normalizer=org_normalizer) as sec_adapter:
        documents.extend(company_adapter.fetch())
        documents.extend(sec_adapter.fetch())

    stats["fetched"] = len(documents)
    if dry_run:
        return stats

    session = SessionLocal()
    try:
        for doc in documents:
            before = session.scalar(
                select(SourceDocument).where(
                    SourceDocument.source_url == doc.source_url,
                    SourceDocument.content_hash == doc.content_hash,
                )
            )
            event = persist_company_document(
                session, doc, asset_resolver=asset_resolver, org_normalizer=org_normalizer
            )
            if before:
                stats["skipped_dup"] += 1
            elif event:
                stats["events"] += 1
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
    return stats


def main() -> None:
    parser = argparse.ArgumentParser(description="Collect company IR and SEC filings")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--init-db", action="store_true")
    args = parser.parse_args()

    if args.init_db:
        from packages.domain.database import Base

        Base.metadata.create_all(create_db_engine())

    stats = run_collect(dry_run=args.dry_run)
    print(
        f"company collect: fetched={stats['fetched']} events={stats['events']} "
        f"skipped_dup={stats.get('skipped_dup', 0)}"
    )


if __name__ == "__main__":
    main()
