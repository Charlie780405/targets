"""周报去重单测。"""

from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from apps.reporter.weekly import save_weekly_report
from packages.domain.enums import ReportType
from packages.domain.models import Report, Target


def test_save_weekly_report_updates_same_period(session: Session) -> None:
    session.add(Target(id="TGT_001", canonical_name="IL-4Rα"))
    session.flush()
    start = date(2026, 7, 19)
    end = date(2026, 7, 25)
    first = save_weekly_report(session, start, end, use_llm=False)
    second = save_weekly_report(session, start, end, use_llm=False)
    assert first.id == second.id
    weekly = list(session.scalars(select(Report).where(Report.report_type == ReportType.WEEKLY)).all())
    assert len(weekly) == 1
