"""周报生成 — 查库 → 合并 → 评分 → LLM/规则抽取 → 渲染模板。"""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from apps.processor.classify import enrich_event_classification
from apps.processor.llm_extract import extract_event_summary, extract_weekly_summary
from apps.processor.merge import MergedEventGroup, apply_merge_to_events
from apps.processor.scoring import (
    confidence_label,
    score_event,
    significance_label,
)
from apps.reporter.weekly_template import (
    KeyConclusion,
    ReportMeta,
    WeeklyBriefContext,
    render_weekly_brief,
)
from packages.domain.enums import EventType, MedicalReviewStatus, ReportType
from packages.domain.models import Event, Evidence, Report, Target


def _evidences_by_event(session: Session, event_ids: list[str]) -> dict[str, list[Evidence]]:
    if not event_ids:
        return {}
    rows = session.scalars(select(Evidence).where(Evidence.event_id.in_(event_ids))).all()
    result: dict[str, list[Evidence]] = {eid: [] for eid in event_ids}
    for ev in rows:
        result.setdefault(ev.event_id, []).append(ev)
    return result


def _query_events(
    session: Session,
    period_start: date,
    period_end: date,
    target_id: str | None,
) -> list[Event]:
    stmt = select(Event).where(Event.event_date >= period_start, Event.event_date <= period_end)
    if target_id:
        stmt = stmt.where(Event.target_id == target_id)
    return list(session.scalars(stmt.order_by(Event.event_date.desc())).all())


def _query_prior_events(session: Session, before: date, target_id: str | None) -> list[Event]:
    stmt = select(Event).where(Event.event_date < before)
    if target_id:
        stmt = stmt.where(Event.target_id == target_id)
    return list(session.scalars(stmt).all())


def score_and_update_events(
    session: Session,
    events: list[Event],
    evidences_by_event: dict[str, list[Evidence]],
    prior_events: list[Event],
    *,
    reference_date: date | None = None,
) -> None:
    """对事件重算三分数并写回（内存 + 可选 flush）。"""
    for event in events:
        et, phase = enrich_event_classification(
            event.event_type, event.title, event.summary, event.phase
        )
        event.event_type = et
        if phase and not event.phase:
            event.phase = phase
        breakdown = score_event(
            event,
            evidences_by_event.get(event.id, []),
            prior_events,
            reference_date=reference_date,
        )
        event.significance_score = breakdown.significance_score
        event.confidence_score = breakdown.confidence_score
        event.novelty_score = breakdown.novelty_score


def _format_bullet(group: MergedEventGroup, extract_summary: str | None = None) -> str:
    ev = group.primary
    sig = significance_label(ev.significance_score or 0.0)
    conf = confidence_label(ev.confidence_score or 0.0)
    src_n = group.source_count
    line = f"**{ev.title}**（{ev.event_date}，显著性{sig}，置信{conf}，{src_n}源）"
    if extract_summary:
        line += f" — {extract_summary[:120]}"
    return line


def build_weekly_context(
    groups: list[MergedEventGroup],
    *,
    period_start: date,
    period_end: date,
    target_name: str = "IL-4Rα",
    use_llm: bool = True,
) -> WeeklyBriefContext:
    """从合并组构建周报上下文。"""
    all_primaries = [g.primary for g in groups]
    period_start_s = period_start.isoformat()
    period_end_s = period_end.isoformat()
    weekly_summary, _ = extract_weekly_summary(all_primaries, period_start_s, period_end_s, use_llm=use_llm)

    key_conclusions: list[KeyConclusion] = []
    trial_changes: list[str] = []
    publications: list[str] = []
    asset_company: list[str] = []
    target_dynamics: list[str] = []
    competitive: list[str] = []
    indication_impact: list[str] = []
    uncertainties: list[str] = []

    for group in groups:
        ev = group.primary
        extract, method = extract_event_summary(ev, group.evidences, use_llm=use_llm)
        sources = [{"name": e.source_name, "url": e.source_url} for e in group.evidences]
        snippet = group.evidences[0].evidence_snippet if group.evidences else None

        bullet = _format_bullet(group, extract.summary_zh)

        if ev.medical_review_status == MedicalReviewStatus.APPROVED:
            key_conclusions.append(
                KeyConclusion(
                    title=ev.title,
                    conclusion=extract.summary_zh,
                    evidence_snippet=snippet,
                    sources=sources,
                    confidence_label=confidence_label(ev.confidence_score or 0.0),
                    impact=extract.impact,
                )
            )
        elif ev.medical_review_status == MedicalReviewStatus.PENDING:
            note = f"待核实：{ev.title}（抽取方式={method}）"
            if extract.uncertainty:
                note += f" — {extract.uncertainty}"
            uncertainties.append(note)

        et = ev.event_type
        if et == EventType.TRIAL_CHANGE:
            trial_changes.append(bullet)
        elif et in (EventType.PUBLICATION, EventType.CONGRESS):
            publications.append(bullet)
        elif et in (EventType.DEAL, EventType.CLINICAL_RESULT):
            asset_company.append(bullet)
        elif et == EventType.REGULATORY:
            competitive.append(bullet)
            indication_impact.append(bullet)
        else:
            target_dynamics.append(bullet)

    return WeeklyBriefContext(
        report=ReportMeta(
            title=f"{target_name} 靶点情报周报（草稿）",
            period_start=period_start_s,
            period_end=period_end_s,
            target=target_name,
            generated_at=datetime.now(tz=UTC).isoformat(timespec="seconds"),
        ),
        key_conclusions=key_conclusions,
        target_dynamics=target_dynamics or ([weekly_summary.executive_summary] if all_primaries else []),
        asset_company_dynamics=asset_company,
        trial_changes=trial_changes,
        publications_congress=publications,
        competitive_landscape=competitive,
        indication_impact=indication_impact,
        watch_next_week=weekly_summary.watch_items,
        evidence_uncertainties=uncertainties,
    )


def generate_weekly_brief(
    session: Session,
    period_start: date,
    period_end: date,
    *,
    target_id: str = "TGT_001",
    use_llm: bool = True,
) -> str:
    """端到端生成周报 Markdown。"""
    target = session.get(Target, target_id)
    target_name = target.canonical_name if target else "IL-4Rα"

    events = _query_events(session, period_start, period_end, target_id)
    prior = _query_prior_events(session, period_start, target_id)
    evidences_map = _evidences_by_event(session, [e.id for e in events])

    score_and_update_events(session, events, evidences_map, prior, reference_date=period_end)
    groups = apply_merge_to_events(events, evidences_map)

    ctx = build_weekly_context(
        groups,
        period_start=period_start,
        period_end=period_end,
        target_name=target_name,
        use_llm=use_llm,
    )
    return render_weekly_brief(ctx)


def save_weekly_report(
    session: Session,
    period_start: date,
    period_end: date,
    *,
    target_id: str = "TGT_001",
    use_llm: bool = True,
) -> Report:
    """生成并落库 Report 记录。"""
    body = generate_weekly_brief(
        session, period_start, period_end, target_id=target_id, use_llm=use_llm
    )
    target = session.get(Target, target_id)
    target_name = target.canonical_name if target else "IL-4Rα"
    report = Report(
        id=f"RPT-{uuid.uuid4().hex[:12]}",
        report_type=ReportType.WEEKLY,
        period_start=period_start,
        period_end=period_end,
        title=f"{target_name} 周报 {period_start.isoformat()}—{period_end.isoformat()}",
        body_markdown=body,
        target_id=target_id,
    )
    session.add(report)
    session.flush()
    return report


def default_week_window(reference: date | None = None) -> tuple[date, date]:
    """默认过去 7 天窗口。"""
    end = reference or datetime.now(tz=UTC).date()
    start = end - timedelta(days=6)
    return start, end
