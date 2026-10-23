"""PLAN-005g-3：WeKnora 来源撤销/失效后，已批准事件也不得再进入周报、已审摘要、审核队列和 Vault。"""

from __future__ import annotations

from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from apps.reporter.approved_digest import export_approved_publications_digest
from apps.reporter.publish import should_export_to_vault
from apps.reporter.review_queue import select_review_queue_event_ids
from apps.reporter.weekly import _query_events
from packages.domain.enums import MedicalReviewStatus
from packages.domain.models import Event, WeKnoraEvidenceProjection

TITLE = "Approved evidence title"


def _approved_weknora_event(
    session: Session,
    *,
    projection_status: str = "active",
    rights_status: str = "verified",
) -> Event:
    event = Event(
        id="EVT-WEKNORA-1",
        event_type="publication",
        event_date=date(2026, 9, 24),
        title=TITLE,
        summary="Historical WeKnora evidence",
        target_id="TGT_001",
        medical_review_status=MedicalReviewStatus.APPROVED,
        content_hash="b" * 64,
    )
    projection = WeKnoraEvidenceProjection(
        id="WK-projection-1",
        knowledge_base_id="kb-1",
        artifact_id="artifact-1",
        sha256="a" * 64,
        contract="weknora.targets.approved-evidence",
        contract_version=1,
        title=TITLE,
        process_status="indexed",
        rights_status=rights_status,
        status=projection_status,
        event_id=event.id,
        payload_json={},
    )
    session.add_all([event, projection])
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
    event = _approved_weknora_event(session)
    assert _visible(session, event, tmp_path) == {"weekly": True, "digest": True, "queue": True, "vault": True}

    projection = session.scalar(select(WeKnoraEvidenceProjection))
    assert projection is not None
    projection.status = "revoked"
    projection.rights_status = "expired"
    session.commit()

    assert _visible(session, event, tmp_path) == {"weekly": False, "digest": False, "queue": False, "vault": False}
    kept = session.get(Event, event.id)
    assert kept is not None, "the event and its audit trail are kept"
    assert kept.medical_review_status == MedicalReviewStatus.APPROVED, "the earlier human decision is not rewritten"


def test_expired_weknora_source_is_blocked_even_if_projection_status_is_active(
    session: Session, tmp_path
) -> None:  # type: ignore[no-untyped-def]
    event = _approved_weknora_event(session, rights_status="expired")

    assert _visible(session, event, tmp_path) == {
        "weekly": False,
        "digest": False,
        "queue": False,
        "vault": False,
    }


def test_events_without_a_weknora_projection_are_unaffected(session: Session, tmp_path) -> None:  # type: ignore[no-untyped-def]
    legacy = Event(
        id="EVT-LEGACY-1", event_type="publication", event_date=date(2026, 9, 24), title="Legacy paper",
        summary="x", target_id="TGT_001", medical_review_status=MedicalReviewStatus.APPROVED, content_hash="h",
    )
    session.add(legacy)
    session.commit()
    assert legacy.id in {e.id for e in _query_events(session, date(2026, 9, 1), date(2026, 9, 30), "TGT_001")}
    assert legacy.id in select_review_queue_event_ids(session)
