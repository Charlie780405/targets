"""审核状态 Vault → DB 回写测试。"""

from datetime import date

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from apps.reporter.review_sync import sync_review_status_from_vault
from packages.domain.database import Base
from packages.domain.enums import EventType, MedicalReviewStatus
from packages.domain.models import Event
from packages.obsidian_exporter.exporter import export_event_note, render_markdown_with_frontmatter


@pytest.fixture
def session() -> Session:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        yield db


def test_sync_review_status_from_vault(session: Session, tmp_path) -> None:
    event = Event(
        id="EVT-2026-00099",
        event_type=EventType.CLINICAL_RESULT,
        event_date=date(2026, 7, 18),
        title="Test event",
        medical_review_status=MedicalReviewStatus.PENDING,
        content_hash="h1",
    )
    session.add(event)
    session.commit()

    vault = tmp_path / "vault"
    export_event_note(event, [], vault)
    note_path = vault / "07-Events/Clinical" / "EVT-2026-00099.md"
    updated = note_path.read_text(encoding="utf-8").replace(
        "review_status: pending",
        "review_status: approved",
    )
    note_path.write_text(updated, encoding="utf-8")

    stats = sync_review_status_from_vault(session, vault)
    session.commit()
    assert stats.updated == 1
    refreshed = session.get(Event, "EVT-2026-00099")
    assert refreshed is not None
    assert refreshed.medical_review_status == MedicalReviewStatus.APPROVED


def test_sync_skips_non_event_notes(session: Session, tmp_path) -> None:
    vault = tmp_path / "vault"
    (vault / "09-Weekly-Briefs").mkdir(parents=True)
    (vault / "09-Weekly-Briefs" / "report.md").write_text(
        render_markdown_with_frontmatter({"report_id": "RPT-1"}, "# Weekly"),
        encoding="utf-8",
    )
    stats = sync_review_status_from_vault(session, vault)
    assert stats.updated == 0
