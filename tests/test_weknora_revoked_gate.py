"""PLAN-005g-3：WeKnora 来源撤销/失效后，已批准事件也不得再进入周报、已审摘要、审核队列和 Vault。"""

from __future__ import annotations

from datetime import UTC, date, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from apps.collector.weknora_literature import sync_collection
from apps.reporter.approved_digest import export_approved_publications_digest
from apps.reporter.publish import should_export_to_vault
from apps.reporter.review_queue import select_review_queue_event_ids
from apps.reporter.weekly import _query_events
from packages.domain.enums import MedicalReviewStatus
from packages.domain.models import Event, WeKnoraEvidenceProjection
from tests.test_weknora_literature import collection, evidence_row

TITLE = "Approved evidence title"


def _approved_weknora_event(session: Session, now: datetime) -> Event:
    sync_collection(session, "kb-1", collection(evidence_row("artifact-1")), now=now)
    projection = session.scalar(select(WeKnoraEvidenceProjection))
    assert projection is not None and projection.event_id
    event = session.get(Event, projection.event_id)
    assert event is not None
    event.medical_review_status = MedicalReviewStatus.APPROVED
    event.target_id = "TGT_001"
    event.event_date = date(2026, 9, 24)
    session.commit()
    return event


def _visible(session: Session, event: Event, tmp_path) -> dict[str, bool]:  # type: ignore[no-untyped-def]
    digest = export_approved_publications_digest(session, tmp_path, use_llm=False)
    return {
        "weekly": event.id in {e.id for e in _query_events(session, date(2026, 9, 1), date(2026, 9, 30), "TGT_001")},
        "digest": TITLE in digest.read_text(encoding="utf-8"),
        "queue": event.id in select_review_queue_event_ids(session),
        "vault": should_export_to_vault(
            session, event, [], review_queue_ids=set(), min_importance=None, min_relevance=0.0
        ),
    }


def test_revoked_weknora_source_removes_an_approved_event_everywhere(session: Session, tmp_path) -> None:  # type: ignore[no-untyped-def]
    now = datetime(2026, 9, 24, tzinfo=UTC)
    event = _approved_weknora_event(session, now)
    assert _visible(session, event, tmp_path) == {"weekly": True, "digest": True, "queue": True, "vault": True}

    sync_collection(session, "kb-1", collection(), now=now)  # WeKnora no longer lists it: revoked / expired / unpublished
    session.commit()

    assert _visible(session, event, tmp_path) == {"weekly": False, "digest": False, "queue": False, "vault": False}
    kept = session.get(Event, event.id)
    assert kept is not None, "the event and its audit trail are kept"
    assert kept.medical_review_status == MedicalReviewStatus.APPROVED, "the earlier human decision is not rewritten"


def test_coming_back_never_restores_an_approval(session: Session, tmp_path) -> None:  # type: ignore[no-untyped-def]
    now = datetime(2026, 9, 24, tzinfo=UTC)
    event = _approved_weknora_event(session, now)
    sync_collection(session, "kb-1", collection(), now=now)
    sync_collection(session, "kb-1", collection(evidence_row("artifact-1")), now=now)
    session.commit()

    refreshed = session.get(Event, event.id)
    assert refreshed is not None
    assert refreshed.medical_review_status == MedicalReviewStatus.PENDING, "a revived source must be reviewed again"
    visible = _visible(session, refreshed, tmp_path)
    assert visible["digest"] is False and visible["weekly"] is True  # listed as pending, not as an approved conclusion


def test_events_without_a_weknora_projection_are_unaffected(session: Session, tmp_path) -> None:  # type: ignore[no-untyped-def]
    legacy = Event(
        id="EVT-LEGACY-1", event_type="publication", event_date=date(2026, 9, 24), title="Legacy paper",
        summary="x", target_id="TGT_001", medical_review_status=MedicalReviewStatus.APPROVED, content_hash="h",
    )
    session.add(legacy)
    session.commit()
    assert legacy.id in {e.id for e in _query_events(session, date(2026, 9, 1), date(2026, 9, 30), "TGT_001")}
    assert legacy.id in select_review_queue_event_ids(session)
