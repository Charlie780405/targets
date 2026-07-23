"""跨源合并单测。"""

from datetime import date

from apps.processor.merge import apply_merge_to_events, merge_events
from packages.domain.enums import EventType, EvidenceLevel
from packages.domain.models import Event, Evidence


def _make_event(
    eid: str,
    *,
    event_date: date,
    asset_id: str = "AST_dupilumab",
    target_id: str = "TGT_001",
    indication_id: str = "IND_ad",
    title: str = "Phase III topline",
    significance: float = 0.5,
) -> Event:
    return Event(
        id=eid,
        event_type=EventType.CLINICAL_RESULT,
        target_id=target_id,
        asset_id=asset_id,
        indication_id=indication_id,
        event_date=event_date,
        title=title,
        significance_score=significance,
        content_hash=f"hash-{eid}",
    )


def test_merge_same_readout_multiple_sources() -> None:
    e1 = _make_event("EVT-1", event_date=date(2026, 7, 18), title="Dupilumab Phase III met endpoint")
    e2 = _make_event(
        "EVT-2",
        event_date=date(2026, 7, 19),
        title="Dupilumab Phase III met endpoint (IR)",
        significance=0.9,
    )
    groups = merge_events([e1, e2])
    assert len(groups) == 1
    assert groups[0].primary.id == "EVT-2"  # higher significance
    assert len(groups[0].members) == 1


def test_no_merge_different_assets() -> None:
    e1 = _make_event("EVT-1", event_date=date(2026, 7, 18), asset_id="AST_dupilumab")
    e2 = _make_event("EVT-2", event_date=date(2026, 7, 18), asset_id="AST_stapokibart")
    groups = merge_events([e1, e2])
    assert len(groups) == 2


def test_no_merge_outside_date_window() -> None:
    e1 = _make_event("EVT-1", event_date=date(2026, 7, 1))
    e2 = _make_event("EVT-2", event_date=date(2026, 7, 20))
    groups = merge_events([e1, e2], window_days=7)
    assert len(groups) == 2


def test_attach_evidences_deduplicates_urls() -> None:
    e1 = _make_event("EVT-1", event_date=date(2026, 7, 18))
    e2 = _make_event("EVT-2", event_date=date(2026, 7, 19))
    ev_a = Evidence(
        id="EVD-a",
        event_id="EVT-1",
        source_name="CT.gov",
        source_url="https://clinicaltrials.gov/1",
        evidence_level=EvidenceLevel.A,
        evidence_snippet="Primary endpoint met.",
        content_hash="a",
    )
    ev_b = Evidence(
        id="EVD-b",
        event_id="EVT-2",
        source_name="Company IR",
        source_url="https://investor.example.com/1",
        evidence_level=EvidenceLevel.B,
        evidence_snippet="Topline positive.",
        content_hash="b",
    )
    groups = apply_merge_to_events(
        [e1, e2],
        {"EVT-1": [ev_a], "EVT-2": [ev_b]},
    )
    assert len(groups) == 1
    assert len(groups[0].evidences) == 2
    assert groups[0].source_count == 2
