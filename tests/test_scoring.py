"""评分规则单测。"""

from datetime import date

from apps.processor.scoring import (
    ScoreBreakdown,
    compute_significance,
    confidence_label,
    score_event,
    significance_label,
)
from packages.domain.enums import EventType, EvidenceLevel, Phase
from packages.domain.models import Event, Evidence


def _event(
    *,
    eid: str = "EVT-test",
    event_type: EventType = EventType.CLINICAL_RESULT,
    phase: Phase | None = None,
    title: str = "Test",
    target_id: str | None = "TGT_001",
    event_date: date | None = None,
) -> Event:
    return Event(
        id=eid,
        event_type=event_type,
        target_id=target_id,
        phase=phase,
        event_date=event_date or date(2026, 7, 20),
        title=title,
        content_hash="abc123",
    )


def _evidence(level: EvidenceLevel = EvidenceLevel.A) -> Evidence:
    return Evidence(
        id="EVD-1",
        event_id="EVT-test",
        source_name="ClinicalTrials.gov",
        source_url="https://example.com/1",
        evidence_level=level,
        evidence_snippet="Primary endpoint met.",
        content_hash="ev1",
    )


def test_phase3_clinical_result_high_significance() -> None:
    event = _event(
        phase=Phase.PHASE_3,
        title="Dupilumab Phase III primary endpoint met in AD",
    )
    sig = compute_significance(event)
    assert sig >= 0.80
    assert significance_label(sig) == "高"


def test_significance_label_tiers() -> None:
    assert significance_label(0.90) == "高"
    assert significance_label(0.60) == "中"
    assert significance_label(0.30) == "低"


def test_confidence_multi_source_boost() -> None:
    event = _event()
    single = score_event(event, [_evidence()])
    multi = score_event(event, [_evidence(), _evidence()])
    assert isinstance(single, ScoreBreakdown)
    assert multi.confidence_score >= single.confidence_score


def test_novelty_duplicate_penalty() -> None:
    event = _event(title="Dupilumab Phase III topline")
    prior = _event(
        eid="EVT-prior",
        title="Dupilumab Phase III topline",
        event_date=date(2026, 7, 10),
    )
    fresh = score_event(event, [_evidence()], [])
    dup = score_event(event, [_evidence()], [prior])
    assert dup.novelty_score < fresh.novelty_score


def test_confidence_label_pending() -> None:
    assert confidence_label(0.50) == "低（待核实）"
