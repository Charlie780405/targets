"""Obsidian 导出器单测。"""

from datetime import date

from packages.domain.enums import EventType, EvidenceLevel, MedicalReviewStatus, Phase
from packages.domain.models import Event, Evidence
from packages.obsidian_exporter.exporter import (
    EntityLabels,
    export_event_note,
    parse_frontmatter,
    render_markdown_with_frontmatter,
)
from packages.obsidian_exporter.vault_layout import ensure_vault_layout, event_note_path


def test_event_frontmatter_and_export(tmp_path) -> None:
    vault = tmp_path / "vault"
    event = Event(
        id="EVT-2026-00031",
        event_type=EventType.CLINICAL_RESULT,
        target_id="TGT_001",
        phase=Phase.PHASE_3,
        event_date=date(2026, 7, 18),
        title="Dupilumab Phase III primary endpoint met",
        summary="Topline positive in AD",
        significance_score=0.95,
        confidence_score=0.91,
        novelty_score=0.8,
        medical_review_status=MedicalReviewStatus.PENDING,
        content_hash="abc",
    )
    evidence = Evidence(
        id="EVD-1",
        event_id=event.id,
        source_name="ClinicalTrials.gov",
        source_url="https://clinicaltrials.gov/study/NCT1",
        evidence_snippet="Primary endpoint met at Week 16.",
        evidence_level=EvidenceLevel.A,
        content_hash="ev1",
    )
    path = export_event_note(
        event,
        [evidence],
        vault,
        labels=EntityLabels(target="IL-4Rα", asset="dupilumab", indication="AD"),
    )
    assert path.exists()
    assert path == event_note_path(vault, event.id, event.event_type)
    text = path.read_text(encoding="utf-8")
    fm = parse_frontmatter(text)
    assert fm["event_id"] == "EVT-2026-00031"
    assert fm["event_type"] == "clinical_result"
    assert fm["target"] == "IL-4Rα"
    assert fm["importance"] == "high"
    assert fm["review_status"] == "pending"
    assert "clinicaltrials.gov" in fm["sources"][0].lower() or fm["sources"] == ["ClinicalTrials.gov"]


def test_vault_layout_creates_dirs(tmp_path) -> None:
    vault = tmp_path / "vault"
    ensure_vault_layout(vault)
    assert (vault / "09-Weekly-Briefs").is_dir()
    assert (vault / "07-Events/Clinical").is_dir()


def test_render_frontmatter_roundtrip() -> None:
    md = render_markdown_with_frontmatter({"event_id": "EVT-1", "review_status": "approved"}, "# Body")
    fm = parse_frontmatter(md)
    assert fm["event_id"] == "EVT-1"
    assert fm["review_status"] == "approved"
