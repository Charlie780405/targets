"""target_link 单元测试。"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from apps.processor.publication_extract import extract_publication_fields
from apps.processor.target_link import backfill_event_target_ids, resolve_target_id_from_matches
from packages.domain.database import Base
from packages.domain.enums import EventType, MedicalReviewStatus
from packages.domain.models import Event


@pytest.fixture
def session() -> Session:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        yield db


def test_resolve_target_id_from_matches_il4ra() -> None:
    target_id = resolve_target_id_from_matches(["IL-4Rα"])
    assert target_id == "TGT_001"


def test_extract_publication_fields_sets_target_id() -> None:
    fields = extract_publication_fields(
        {"title": "Dupilumab blocks IL-4Rα signaling in atopic dermatitis", "abstract": None}
    )
    assert fields["target_id"] == "TGT_001"
    assert "IL-4Rα" in fields["matched_targets"]


def test_backfill_event_target_ids(session: Session) -> None:
    event = Event(
        id="EVT-TEST-00001",
        event_type=EventType.PUBLICATION,
        event_date=datetime.now(tz=UTC).date(),
        discovered_at=datetime.now(tz=UTC),
        title="Test",
        summary="study_type=review; targets=IL-4Rα",
        medical_review_status=MedicalReviewStatus.PENDING,
        source_count=1,
        content_hash="abc",
    )
    session.add(event)
    session.flush()
    assert backfill_event_target_ids(session) == 1
    assert event.target_id == "TGT_001"
