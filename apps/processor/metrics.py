"""采集覆盖率、重复率、人工接受率评估。"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from pathlib import Path

import yaml  # type: ignore[import-untyped]
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from packages.domain.enums import MedicalReviewStatus
from packages.domain.models import Event, SourceDocument

_ROOT = Path(__file__).resolve().parents[2]
_SOURCES_DIR = _ROOT / "config" / "sources"


@dataclass(frozen=True)
class MetricsReport:
    period_start: date
    period_end: date
    event_count: int
    source_document_count: int
    configured_sources: int
    coverage_ratio: float
    duplicate_ratio: float
    acceptance_ratio: float
    pending_count: int
    approved_count: int
    rejected_count: int


def _count_configured_sources() -> int:
    count = 0
    if _SOURCES_DIR.is_dir():
        for path in _SOURCES_DIR.glob("*.yaml"):
            raw = yaml.safe_load(path.read_text(encoding="utf-8"))
            if isinstance(raw, dict) and raw.get("source_id"):
                count += 1
    return max(count, 1)


def compute_metrics(
    session: Session,
    period_start: date,
    period_end: date,
) -> MetricsReport:
    events = list(
        session.scalars(
            select(Event).where(Event.event_date >= period_start, Event.event_date <= period_end)
        ).all()
    )
    event_count = len(events)
    source_doc_count = int(session.scalar(select(func.count()).select_from(SourceDocument)) or 0)

    configured = _count_configured_sources()
    distinct_source_ids = session.scalar(
        select(func.count(func.distinct(SourceDocument.source_id)))
    ) or 0
    coverage_ratio = min(1.0, distinct_source_ids / configured)

    multi_source = sum(1 for e in events if (e.source_count or 0) > 1)
    duplicate_ratio = multi_source / event_count if event_count else 0.0

    approved = sum(1 for e in events if e.medical_review_status == MedicalReviewStatus.APPROVED)
    rejected = sum(1 for e in events if e.medical_review_status == MedicalReviewStatus.REJECTED)
    pending = sum(1 for e in events if e.medical_review_status == MedicalReviewStatus.PENDING)
    reviewed = approved + rejected
    acceptance_ratio = approved / reviewed if reviewed else 0.0

    return MetricsReport(
        period_start=period_start,
        period_end=period_end,
        event_count=event_count,
        source_document_count=int(source_doc_count),
        configured_sources=configured,
        coverage_ratio=round(coverage_ratio, 3),
        duplicate_ratio=round(duplicate_ratio, 3),
        acceptance_ratio=round(acceptance_ratio, 3),
        pending_count=pending,
        approved_count=approved,
        rejected_count=rejected,
    )


def format_metrics_markdown(report: MetricsReport) -> str:
    return "\n".join(
        [
            f"# 情报指标 {report.period_start} — {report.period_end}",
            "",
            f"- 事件数：{report.event_count}",
            f"- 来源文档数：{report.source_document_count}",
            f"- 配置源数：{report.configured_sources}",
            f"- **覆盖率**：{report.coverage_ratio:.1%}（活跃源/配置源）",
            f"- **多源重复率**：{report.duplicate_ratio:.1%}（多源事件/总事件）",
            f"- **人工接受率**：{report.acceptance_ratio:.1%}（approved/已审）",
            f"- 待审 pending：{report.pending_count}；已通过：{report.approved_count}；拒绝：{report.rejected_count}",
        ]
    )
