"""LLM 抽取降级与周报端到端测试。"""

from datetime import UTC, date, datetime

import pytest
from pydantic import ValidationError
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from apps.processor.llm_extract import (
    EventExtractResult,
    extract_event_summary,
    validate_event_extract,
)
from apps.reporter.weekly import build_weekly_context, generate_weekly_brief
from packages.domain.content_hash import compute_content_hash
from packages.domain.database import Base
from packages.domain.enums import EventType, EvidenceLevel, MedicalReviewStatus, Phase
from packages.domain.models import Event, Evidence, Target


@pytest.fixture
def session() -> Session:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        yield db


def test_llm_schema_rejection_falls_back_to_rule() -> None:
    with pytest.raises(ValidationError):
        validate_event_extract({"summary_zh": "", "impact": "x"})

    event = Event(
        id="EVT-1",
        event_type=EventType.CLINICAL_RESULT,
        target_id="TGT_001",
        phase=Phase.PHASE_3,
        event_date=date(2026, 7, 18),
        title="Phase III primary endpoint met",
        content_hash="h1",
    )
    ev = Evidence(
        id="EVD-1",
        event_id="EVT-1",
        source_name="Test",
        source_url="https://example.com",
        evidence_level=EvidenceLevel.B,
        evidence_snippet="Met primary endpoint.",
        content_hash="e1",
    )
    result, method = extract_event_summary(event, [ev], use_llm=False)
    assert method == "rule"
    assert isinstance(result, EventExtractResult)
    assert "Phase III" in event.title or result.summary_zh


def test_generate_weekly_brief_e2e(session: Session) -> None:
    target = Target(id="TGT_001", canonical_name="IL-4Rα")
    session.add(target)
    session.flush()

    content = {"title": "Phase III topline"}
    event = Event(
        id="EVT-2026-00099",
        event_type=EventType.CLINICAL_RESULT,
        target_id="TGT_001",
        asset_id="AST_dupilumab",
        phase=Phase.PHASE_3,
        event_date=date(2026, 7, 18),
        discovered_at=datetime(2026, 7, 18, 12, 0, tzinfo=UTC),
        title="Dupilumab Phase III primary endpoint met in AD",
        medical_review_status=MedicalReviewStatus.PENDING,
        source_count=1,
        content_hash=compute_content_hash(content),
    )
    session.add(event)
    session.flush()

    evidence = Evidence(
        id="EVD-99",
        event_id="EVT-2026-00099",
        source_name="ClinicalTrials.gov",
        source_url="https://clinicaltrials.gov/study/NCT00000099",
        evidence_snippet="Primary endpoint met at Week 16 (EASI-75).",
        evidence_level=EvidenceLevel.A,
        content_hash=compute_content_hash("snippet"),
    )
    session.add(evidence)
    session.commit()

    md = generate_weekly_brief(
        session,
        date(2026, 7, 14),
        date(2026, 7, 21),
        target_id="TGT_001",
        use_llm=False,
    )
    assert "IL-4Rα" in md
    assert "Dupilumab" in md
    assert "待核实" in md or "证据" in md


def test_build_weekly_context_approved_key_conclusion(session: Session) -> None:
    from apps.processor.merge import MergedEventGroup

    event = Event(
        id="EVT-approved",
        event_type=EventType.CLINICAL_RESULT,
        target_id="TGT_001",
        phase=Phase.PHASE_3,
        event_date=date(2026, 7, 18),
        title="Approved conclusion event",
        significance_score=0.95,
        confidence_score=0.90,
        medical_review_status=MedicalReviewStatus.APPROVED,
        content_hash="h2",
    )
    ev = Evidence(
        id="EVD-ap",
        event_id="EVT-approved",
        source_name="FDA",
        source_url="https://fda.gov/1",
        evidence_level=EvidenceLevel.A,
        evidence_snippet="Approved.",
        content_hash="e2",
    )
    group = MergedEventGroup(primary=event, evidences=[ev])
    ctx = build_weekly_context(
        [group],
        period_start=date(2026, 7, 14),
        period_end=date(2026, 7, 21),
        use_llm=False,
    )
    assert len(ctx.key_conclusions) == 1
    assert ctx.key_conclusions[0].title == "Approved conclusion event"
