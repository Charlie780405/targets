"""指标评估与健康检查测试。"""

from datetime import date

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from apps.health import git_head_sha, health_payload
from apps.processor.metrics import compute_metrics, format_metrics_markdown
from packages.domain.database import Base
from packages.domain.enums import EventType, MedicalReviewStatus
from packages.domain.models import Event, SourceDocument


@pytest.fixture
def session() -> Session:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        yield db


def test_compute_metrics(session: Session) -> None:
    session.add(
        Event(
            id="EVT-1",
            event_type=EventType.CLINICAL_RESULT,
            event_date=date(2026, 7, 18),
            title="E1",
            medical_review_status=MedicalReviewStatus.APPROVED,
            source_count=2,
            content_hash="h1",
        )
    )
    session.add(
        Event(
            id="EVT-2",
            event_type=EventType.DEAL,
            event_date=date(2026, 7, 19),
            title="E2",
            medical_review_status=MedicalReviewStatus.PENDING,
            source_count=1,
            content_hash="h2",
        )
    )
    session.add(
        SourceDocument(
            id="SD-1",
            source_id="clinicaltrials",
            source_name="CT",
            source_url="https://example.com/1",
            content_hash="c1",
        )
    )
    session.commit()

    report = compute_metrics(session, date(2026, 7, 14), date(2026, 7, 21))
    assert report.event_count == 2
    assert report.approved_count == 1
    assert report.pending_count == 1
    assert "覆盖率" in format_metrics_markdown(report)


def test_health_payload(session: Session) -> None:
    engine = session.get_bind()
    payload = health_payload(engine)  # type: ignore[arg-type]
    assert payload["database"] == "up"
    assert payload["status"] == "ok"
    assert git_head_sha() is not None or payload["version"] is None
