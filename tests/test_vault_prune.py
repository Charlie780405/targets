"""Vault prune 单测 — 002b 挡弱相关文献在 Vault 外。"""

from datetime import date

from apps.reporter.publish import prune_vault_publications
from packages.domain.enums import EventType, EvidenceLevel, MedicalReviewStatus
from packages.domain.models import Event, Evidence, Publication
from packages.obsidian_exporter.exporter import export_event_note
from sqlalchemy.orm import Session


def test_prune_removes_low_relevance_publication(tmp_path, session: Session) -> None:
    vault = tmp_path / "vault"
    pub = Publication(
        id="PMID-1",
        pmid="1",
        title="General dermatology",
        abstract="Unrelated topic.",
        content_hash="h1",
    )
    session.add(pub)
    event = Event(
        id="EVT-2026-00001",
        event_type=EventType.PUBLICATION,
        event_date=date(2026, 7, 1),
        title=pub.title,
        summary="study_type=other",
        significance_score=0.55,
        medical_review_status=MedicalReviewStatus.PENDING,
        content_hash="h2",
    )
    session.add(event)
    evidence = Evidence(
        id="EVD-PM-PMID-1",
        event_id=event.id,
        source_name="PubMed",
        source_url="https://pubmed.ncbi.nlm.nih.gov/1/",
        evidence_level=EvidenceLevel.B,
        content_hash="h3",
    )
    session.add(evidence)
    session.flush()

    export_event_note(event, [evidence], vault, session=session)
    note = vault / "06-Publications" / "EVT-2026-00001.md"
    assert note.is_file()

    pruned = prune_vault_publications(
        session,
        vault,
        min_importance="medium",
        min_relevance=0.45,
    )
    assert pruned == 1
    assert not note.exists()
