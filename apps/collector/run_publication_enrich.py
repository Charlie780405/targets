"""批量文献 LLM/规则分析，写入 SourceDocument.payload_json.analysis。"""

from __future__ import annotations

import argparse
import re

from sqlalchemy import select
from sqlalchemy.orm import Session

from apps.processor.publication_analysis import analysis_to_payload, analyze_publication
from packages.domain.database import SessionLocal
from packages.domain.enums import EventType, MedicalReviewStatus
from packages.domain.models import Event, Evidence, Publication, SourceDocument


def _study_type_from_summary(summary: str | None) -> str:
    if not summary:
        return "other"
    match = re.search(r"study_type=([^;]+)", summary)
    return match.group(1).strip() if match else "other"


def _targets_from_summary(summary: str | None) -> list[str]:
    if not summary:
        return []
    match = re.search(r"targets=([^;]+)", summary)
    if not match:
        return []
    return [t.strip() for t in match.group(1).split(",") if t.strip()]


def _resolve_publication(session: Session, event: Event, evidences: list[Evidence]) -> Publication | None:
    for evidence in evidences:
        if evidence.id.startswith("EVD-PM-"):
            pub = session.get(Publication, evidence.id.removeprefix("EVD-PM-"))
            if pub:
                return pub
    return session.scalar(select(Publication).where(Publication.title == event.title).limit(1))


def enrich_publication_events(
    session: Session,
    *,
    use_llm: bool = True,
    limit: int = 50,
    event_ids: set[str] | None = None,
) -> dict[str, int]:
    stats = {"scanned": 0, "enriched": 0, "skipped": 0}
    stmt = select(Event).where(
        Event.event_type == EventType.PUBLICATION,
        Event.medical_review_status == MedicalReviewStatus.PENDING,
    )
    if event_ids:
        stmt = stmt.where(Event.id.in_(event_ids))
    stmt = stmt.order_by(Event.event_date.desc()).limit(limit)
    events = list(session.scalars(stmt).all())
    for event in events:
        stats["scanned"] += 1
        evidences = list(session.scalars(select(Evidence).where(Evidence.event_id == event.id)).all())
        publication = _resolve_publication(session, event, evidences)
        if publication is None:
            stats["skipped"] += 1
            continue
        sdoc_id = f"SDOC-PM-{publication.id}"
        sdoc = session.get(SourceDocument, sdoc_id)
        if sdoc and isinstance(sdoc.payload_json, dict):
            if sdoc.payload_json.get("analysis"):
                stats["skipped"] += 1
                continue
        elif sdoc is None:
            stats["skipped"] += 1
            continue
        study_type = _study_type_from_summary(event.summary)
        targets = _targets_from_summary(event.summary)
        result, _method = analyze_publication(
            title=publication.title,
            abstract=publication.abstract,
            doi=publication.doi,
            pmid=publication.pmid,
            study_type=study_type,
            matched_targets=targets,
            use_llm=use_llm,
        )
        payload = dict(sdoc.payload_json) if sdoc and sdoc.payload_json else {}
        payload["analysis"] = analysis_to_payload(result)
        if sdoc:
            sdoc.payload_json = payload
        stats["enriched"] += 1
    session.flush()
    return stats


def main() -> None:
    from packages.domain.env import load_project_env

    load_project_env()
    parser = argparse.ArgumentParser(description="Enrich publication events with analysis")
    parser.add_argument("--no-llm", action="store_true")
    parser.add_argument("--limit", type=int, default=50)
    args = parser.parse_args()

    session = SessionLocal()
    try:
        stats = enrich_publication_events(session, use_llm=not args.no_llm, limit=args.limit)
        session.commit()
        print(
            f"publication enrich: scanned={stats['scanned']} enriched={stats['enriched']} "
            f"skipped={stats['skipped']}"
        )
    finally:
        session.close()


if __name__ == "__main__":
    main()
