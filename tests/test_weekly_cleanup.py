"""空周报清理单测。"""

from datetime import date, datetime, timezone
from pathlib import Path

from sqlalchemy.orm import Session

from apps.reporter.weekly_cleanup import (
    cleanup_weekly_briefs,
    dedupe_weekly_reports_in_db,
    is_empty_weekly_brief,
    prune_weekly_brief_files,
)
from packages.domain.enums import ReportType
from packages.domain.models import Report, Target
from packages.obsidian_exporter.vault_layout import weekly_note_path


EMPTY_BODY = """# IL-4Rα 靶点情报周报（草稿）

## 1. 本周关键结论

_本周暂无已审核（approved）关键结论。_

## 2. 靶点级动态

_暂无。_

## 5. 论文与大会数据

_暂无。_
"""

SUBSTANTIVE_BODY = """# IL-4Rα 靶点情报周报（草稿）

## 1. 本周关键结论

_本周暂无已审核（approved）关键结论。_

## 2. 靶点级动态

- 本周共 1 条事件：Example drug update.

## 5. 论文与大会数据

- **Example paper.**（2026-07-23，显著性中，置信高，1源）
"""


def test_is_empty_weekly_brief() -> None:
    assert is_empty_weekly_brief(EMPTY_BODY) is True
    assert is_empty_weekly_brief(SUBSTANTIVE_BODY) is False


def _add_weekly(session: Session, report_id: str, body: str, *, generated_at: datetime) -> None:
    session.add(
        Report(
            id=report_id,
            report_type=ReportType.WEEKLY,
            period_start=date(2026, 7, 19),
            period_end=date(2026, 7, 25),
            title="IL-4Rα 周报",
            target_id="TGT_001",
            body_markdown=body,
            generated_at=generated_at,
        )
    )


def test_dedupe_weekly_reports_in_db(session: Session) -> None:
    session.add(Target(id="TGT_001", canonical_name="IL-4Rα"))
    session.flush()
    _add_weekly(
        session,
        "RPT-old",
        EMPTY_BODY,
        generated_at=datetime(2026, 7, 25, 10, tzinfo=timezone.utc),
    )
    _add_weekly(
        session,
        "RPT-new",
        SUBSTANTIVE_BODY,
        generated_at=datetime(2026, 7, 25, 12, tzinfo=timezone.utc),
    )
    session.flush()
    removed = dedupe_weekly_reports_in_db(session)
    assert removed == 1
    assert session.get(Report, "RPT-new") is not None
    assert session.get(Report, "RPT-old") is None


def test_prune_weekly_brief_files(tmp_path: Path) -> None:
    brief_dir = tmp_path / "09-Weekly-Briefs"
    brief_dir.mkdir(parents=True)
    empty_path = weekly_note_path(tmp_path, "RPT-empty", "2026-07-19")
    keep_path = weekly_note_path(tmp_path, "RPT-keep", "2026-07-19")
    empty_path.parent.mkdir(parents=True, exist_ok=True)
    empty_path.write_text(
        "---\nreport_id: RPT-empty\n---\n" + EMPTY_BODY,
        encoding="utf-8",
    )
    keep_path.write_text(
        "---\nreport_id: RPT-keep\n---\n" + SUBSTANTIVE_BODY,
        encoding="utf-8",
    )
    pruned = prune_weekly_brief_files(tmp_path, keep_report_ids={"RPT-keep"})
    assert pruned == 1
    assert not empty_path.exists()
    assert keep_path.exists()


def test_cleanup_weekly_briefs(session: Session, tmp_path: Path) -> None:
    session.add(Target(id="TGT_001", canonical_name="IL-4Rα"))
    session.flush()
    _add_weekly(
        session,
        "RPT-empty",
        EMPTY_BODY,
        generated_at=datetime(2026, 7, 25, 10, tzinfo=timezone.utc),
    )
    brief_dir = tmp_path / "09-Weekly-Briefs"
    brief_dir.mkdir(parents=True)
    stale = weekly_note_path(tmp_path, "RPT-stale", "2026-07-19")
    stale.write_text("---\nreport_id: RPT-stale\n---\n" + EMPTY_BODY, encoding="utf-8")
    result = cleanup_weekly_briefs(session, tmp_path)
    assert result["db_removed"] == 1
    assert result["vault_pruned"] == 1
    assert result["keep_count"] == 0
    assert session.get(Report, "RPT-empty") is None
    assert not stale.exists()
