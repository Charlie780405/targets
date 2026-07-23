"""ClinicalTrials.gov 采集入口 — 供 cron/systemd 定时调用。"""

from __future__ import annotations

import argparse
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from apps.processor.trial_diff import (
    build_trial_change_event,
    diff_snapshots,
    is_medically_meaningful_change,
)
from packages.domain.database import SessionLocal, create_db_engine
from packages.domain.models import Event, SourceDocument, Trial, TrialSnapshot
from packages.source_adapters.base import FetchedDocument
from packages.source_adapters.clinicaltrials.adapter import ClinicalTrialsAdapter
from packages.source_adapters.clinicaltrials.parser import parse_trial_record


def _next_event_id(session: Session, year: int) -> str:
    prefix = f"EVT-{year}-"
    rows = session.scalars(select(Event.id).where(Event.id.like(f"{prefix}%"))).all()
    max_seq = 0
    for event_id in rows:
        try:
            max_seq = max(max_seq, int(str(event_id).split("-")[-1]))
        except ValueError:
            continue
    return f"{prefix}{max_seq + 1:05d}"


def persist_study(
    session: Session,
    doc: FetchedDocument,
    *,
    raw_path: Path | None = None,
) -> tuple[Trial, TrialSnapshot | None, Event | None]:
    """落库 Trial + Snapshot；若有有意义 diff 则返回 trial_change Event。"""
    parsed = parse_trial_record(doc.payload)
    watch_fields = parsed.pop("watch_fields")
    watch_fields_hash = parsed.pop("watch_fields_hash")

    trial = session.get(Trial, parsed["id"])
    if trial is None:
        trial = Trial(**parsed)
        if raw_path:
            trial.raw_snapshot_path = str(raw_path)
        session.add(trial)
    else:
        for key, value in parsed.items():
            if key != "id":
                setattr(trial, key, value)
        if raw_path:
            trial.raw_snapshot_path = str(raw_path)

    session.flush()

    previous = session.scalar(
        select(TrialSnapshot)
        .where(TrialSnapshot.trial_id == trial.id)
        .order_by(TrialSnapshot.snapshot_at.desc())
        .limit(1)
    )

    if previous and previous.watch_fields_hash == watch_fields_hash:
        return trial, None, None

    snapshot = TrialSnapshot(
        trial_id=trial.id,
        content_hash=doc.content_hash,
        payload_json=watch_fields,
        watch_fields_hash=watch_fields_hash,
    )
    session.add(snapshot)
    session.flush()

    source_doc = SourceDocument(
        id=f"SDOC-CT-{trial.id}-{snapshot.id}",
        source_id=doc.source_id,
        source_name=doc.source_name,
        source_url=doc.source_url,
        title=doc.title,
        fetched_at=datetime.now(tz=UTC),
        content_hash=doc.content_hash,
        raw_path=str(raw_path) if raw_path else None,
        payload_json=doc.payload,
    )
    session.add(source_doc)

    changes = diff_snapshots(previous, watch_fields)
    event: Event | None = None
    if changes and is_medically_meaningful_change(changes):
        event = build_trial_change_event(
            trial,
            changes,
            event_id=_next_event_id(session, datetime.now(tz=UTC).year),
        )
        session.add(event)

    return trial, snapshot, event


def run_collect(*, dry_run: bool = False) -> dict[str, int]:
    stats = {"fetched": 0, "trials": 0, "snapshots": 0, "events": 0}
    with ClinicalTrialsAdapter() as adapter:
        documents = adapter.fetch()

    stats["fetched"] = len(documents)
    if dry_run:
        return stats

    session = SessionLocal()
    try:
        for doc in documents:
            _trial, snapshot, event = persist_study(session, doc)
            stats["trials"] += 1
            if snapshot:
                stats["snapshots"] += 1
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
    parser = argparse.ArgumentParser(description="Collect ClinicalTrials.gov studies")
    parser.add_argument("--dry-run", action="store_true", help="Fetch only, do not write DB")
    parser.add_argument("--init-db", action="store_true", help="Create tables before collect")
    args = parser.parse_args()

    if args.init_db:
        from packages.domain.database import Base

        Base.metadata.create_all(create_db_engine())

    stats = run_collect(dry_run=args.dry_run)
    print(
        f"clinicaltrials collect: fetched={stats['fetched']} "
        f"trials={stats['trials']} snapshots={stats['snapshots']} events={stats['events']}"
    )


if __name__ == "__main__":
    main()
