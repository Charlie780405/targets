"""领域模型往返测试。"""

from datetime import UTC, date, datetime

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from packages.domain.content_hash import compute_content_hash
from packages.domain.database import Base
from packages.domain.enums import EventType, EvidenceLevel, MedicalReviewStatus
from packages.domain.models import Event, Evidence, SourceDocument, Target


@pytest.fixture
def session() -> Session:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        yield db


def test_target_roundtrip(session: Session) -> None:
    target = Target(
        id="TGT_001",
        canonical_name="IL-4Rα",
        gene="IL4R",
    )
    session.add(target)
    session.commit()
    loaded = session.get(Target, "TGT_001")
    assert loaded is not None
    assert loaded.canonical_name == "IL-4Rα"
    assert loaded.gene == "IL4R"


def test_event_with_evidence(session: Session) -> None:
    target = Target(id="TGT_001", canonical_name="IL-4Rα")
    session.add(target)
    session.flush()

    content = {"title": "Phase 2 primary endpoint met", "nct": "NCT00000001"}
    event = Event(
        id="EVT-2026-00001",
        event_type=EventType.CLINICAL_RESULT,
        target_id="TGT_001",
        event_date=date(2026, 7, 18),
        discovered_at=datetime(2026, 7, 18, 12, 0, tzinfo=UTC),
        title="某公司 IL-4Rα 抗体 II 期达到主要终点",
        significance_score=0.9,
        confidence_score=0.85,
        novelty_score=0.7,
        medical_review_status=MedicalReviewStatus.PENDING,
        source_count=1,
        content_hash=compute_content_hash(content),
    )
    session.add(event)
    session.flush()

    source_doc = SourceDocument(
        id="SDOC-001",
        source_id="clinicaltrials",
        source_name="ClinicalTrials.gov",
        source_url="https://clinicaltrials.gov/study/NCT00000001",
        content_hash=compute_content_hash(content),
    )
    session.add(source_doc)
    session.flush()

    evidence = Evidence(
        id="EVD-001",
        event_id="EVT-2026-00001",
        source_document_id="SDOC-001",
        source_name="ClinicalTrials.gov",
        source_url="https://clinicaltrials.gov/study/NCT00000001",
        evidence_snippet="Primary endpoint met at Week 16.",
        evidence_level=EvidenceLevel.A,
        content_hash=compute_content_hash("Primary endpoint met at Week 16."),
    )
    session.add(evidence)
    session.commit()

    loaded = session.get(Event, "EVT-2026-00001")
    assert loaded is not None
    assert loaded.event_type == EventType.CLINICAL_RESULT
    assert loaded.significance_score == 0.9
    assert len(loaded.evidences) == 1
    assert loaded.evidences[0].evidence_level == EvidenceLevel.A


def test_content_hash_stable() -> None:
    payload = {"b": 2, "a": 1}
    assert compute_content_hash(payload) == compute_content_hash({"a": 1, "b": 2})
    assert compute_content_hash("hello") != compute_content_hash("world")
