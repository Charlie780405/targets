"""Vault publish pipeline 单测。"""

from datetime import date
from pathlib import Path
from unittest.mock import patch

from sqlalchemy.orm import Session

from apps.reporter.vault_publish_pipeline import (
    publish_use_llm_default,
    run_vault_publish_pipeline,
)
from packages.domain.enums import EventType, MedicalReviewStatus
from packages.domain.models import Event, Target


def test_publish_use_llm_default(monkeypatch) -> None:
    monkeypatch.delenv("PUBLISH_USE_LLM", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    assert publish_use_llm_default() is False
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    assert publish_use_llm_default() is True
    monkeypatch.setenv("PUBLISH_USE_LLM", "false")
    assert publish_use_llm_default() is False


def test_pipeline_skips_when_no_changes(session: Session, tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    with patch("apps.reporter.vault_publish_pipeline.pull_vault", return_value=False):
        stats = run_vault_publish_pipeline(session, vault, pull=True, force=False)
    assert stats.skipped is True


def test_pipeline_runs_after_review_sync(session: Session, tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    (vault / "06-Publications").mkdir(parents=True)
    session.add(Target(id="TGT_001", canonical_name="IL-4Rα"))
    session.add(
        Event(
            id="EVT-2026-00099",
            event_type=EventType.PUBLICATION,
            title="Dupilumab trial",
            event_date=date(2026, 1, 1),
            target_id="TGT_001",
            medical_review_status=MedicalReviewStatus.PENDING,
            summary="study_type=clinical_trial",
            content_hash="abc123",
            source_count=1,
        )
    )
    session.flush()
    note = vault / "06-Publications" / "EVT-2026-00099.md"
    note.write_text(
        "---\nevent_id: EVT-2026-00099\nreview_status: approved\n---\n# Dupilumab\n",
        encoding="utf-8",
    )
    with (
        patch("apps.reporter.vault_publish_pipeline.pull_vault", return_value=False),
        patch("apps.reporter.vault_publish_pipeline.publish_vault") as mock_pub,
    ):
        mock_pub.return_value.events_exported = 1
        mock_pub.return_value.reports_exported = 1
        mock_pub.return_value.git_pushed = True
        mock_pub.return_value.events_skipped = 0
        mock_pub.return_value.vault_pruned = 0
        mock_pub.return_value.weekly_briefs_pruned = 0
        stats = run_vault_publish_pipeline(
            session, vault, pull=False, force=False, use_llm=False, enrich_publications=False
        )
    assert stats.skipped is False
    assert stats.review_updated == 1
    event = session.get(Event, "EVT-2026-00099")
    assert event is not None
    assert event.medical_review_status == MedicalReviewStatus.APPROVED
