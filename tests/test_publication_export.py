"""Publication 富导出单测。"""

from datetime import date

from sqlalchemy.orm import Session

from packages.domain.enums import EventType, EvidenceLevel, MedicalReviewStatus
from packages.domain.models import Event, Evidence, Publication, SourceDocument
from packages.obsidian_exporter.exporter import export_event_note, parse_frontmatter
from packages.obsidian_exporter.publication_context import resolve_publication_export_context


def test_resolve_publication_context(session: Session) -> None:
    pub = Publication(
        id="PMID-12345",
        pmid="12345",
        doi="10.1000/test",
        title="IL-4Rα blockade in AD",
        abstract="Full abstract text here.",
        published_at=date(2026, 7, 1),
        content_hash="abc",
    )
    session.add(pub)
    session.flush()
    event = Event(
        id="EVT-2026-00099",
        event_type=EventType.PUBLICATION,
        event_date=date(2026, 7, 1),
        title=pub.title,
        summary="study_type=clinical_trial; targets=IL-4Rα",
        target_id="TGT_001",
        medical_review_status=MedicalReviewStatus.PENDING,
        content_hash="ev",
    )
    session.add(event)
    sdoc = SourceDocument(
        id="SDOC-PM-PMID-12345",
        source_id="pubmed",
        source_name="PubMed",
        source_url="https://pubmed.ncbi.nlm.nih.gov/12345/",
        content_hash="abc",
        payload_json={"pmid": "12345", "analysis": {"summary_zh": "中文研判草稿"}},
    )
    session.add(sdoc)
    evidence = Evidence(
        id="EVD-PM-PMID-12345",
        event_id=event.id,
        source_document_id=sdoc.id,
        source_name="PubMed",
        source_url="https://pubmed.ncbi.nlm.nih.gov/12345/",
        evidence_snippet="snippet",
        evidence_level=EvidenceLevel.B,
        content_hash="ev1",
    )
    session.add(evidence)
    session.flush()

    ctx = resolve_publication_export_context(session, event, [evidence])
    assert ctx is not None
    assert ctx.doi == "10.1000/test"
    assert ctx.analysis_zh == "中文研判草稿"


def test_export_publication_note(tmp_path, session: Session) -> None:
    pub = Publication(
        id="PMID-999",
        pmid="999",
        doi="10.1000/x",
        title="Dupilumab and IL-4Rα",
        abstract="Abstract body.",
        published_at=date(2026, 7, 10),
        content_hash="h1",
    )
    session.add(pub)
    event = Event(
        id="EVT-2026-00100",
        event_type=EventType.PUBLICATION,
        event_date=date(2026, 7, 10),
        title=pub.title,
        summary="study_type=review; targets=IL-4Rα",
        significance_score=0.55,
        medical_review_status=MedicalReviewStatus.PENDING,
        content_hash="h2",
    )
    session.add(event)
    evidence = Evidence(
        id="EVD-PM-PMID-999",
        event_id=event.id,
        source_name="PubMed",
        source_url="https://pubmed.ncbi.nlm.nih.gov/999/",
        evidence_level=EvidenceLevel.B,
        content_hash="h3",
    )
    session.add(evidence)
    session.flush()

    path = export_event_note(event, [evidence], tmp_path / "vault", session=session)
    text = path.read_text(encoding="utf-8")
    fm = parse_frontmatter(text)
    assert fm["pmid"] == "999"
    assert fm["doi"] == "10.1000/x"
    assert "https://doi.org/10.1000/x" in text
    assert "## 摘要（原文）" in text
    assert "Abstract body." in text
