"""Dashboard 导出单测。"""

from datetime import date

from sqlalchemy.orm import Session

from apps.reporter.dashboard import export_pending_review_dashboard
from packages.domain.enums import EventType, MedicalReviewStatus
from packages.domain.models import Event


def test_export_pending_dashboard(tmp_path, session: Session) -> None:
    session.add(
        Event(
            id="EVT-2026-00050",
            event_type=EventType.PUBLICATION,
            event_date=date(2026, 7, 20),
            title="Pending paper",
            significance_score=0.6,
            medical_review_status=MedicalReviewStatus.PENDING,
            content_hash="x",
        )
    )
    session.flush()
    path = export_pending_review_dashboard(session, tmp_path / "vault")
    text = path.read_text(encoding="utf-8")
    assert "待审队列" in text
    assert "EVT-2026-00050" in text
