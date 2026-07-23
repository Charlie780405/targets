"""周报 Markdown 渲染 — 空数据不报错。"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

_TEMPLATES_DIR = Path(__file__).resolve().parents[2] / "templates"


def _today_iso() -> str:
    return datetime.now(tz=UTC).date().isoformat()


def _now_iso() -> str:
    return datetime.now(tz=UTC).isoformat(timespec="seconds")


@dataclass
class ReportMeta:
    title: str
    period_start: date | str
    period_end: date | str
    target: str
    generated_at: datetime | str = field(default_factory=_now_iso)


@dataclass
class KeyConclusion:
    title: str
    conclusion: str
    evidence_snippet: str | None = None
    sources: list[dict[str, str]] = field(default_factory=list)
    confidence_label: str | None = None
    impact: str | None = None


def _default_report() -> ReportMeta:
    return ReportMeta(
        title="靶点情报周报（草稿）",
        period_start=_today_iso(),
        period_end=_today_iso(),
        target="IL-4Rα",
    )


@dataclass
class WeeklyBriefContext:
    report: ReportMeta = field(default_factory=_default_report)
    key_conclusions: list[KeyConclusion] = field(default_factory=list)
    target_dynamics: list[str] = field(default_factory=list)
    asset_company_dynamics: list[str] = field(default_factory=list)
    trial_changes: list[str] = field(default_factory=list)
    publications_congress: list[str] = field(default_factory=list)
    competitive_landscape: list[str] = field(default_factory=list)
    indication_impact: list[str] = field(default_factory=list)
    watch_next_week: list[str] = field(default_factory=list)
    evidence_uncertainties: list[str] = field(default_factory=list)


def _env() -> Environment:
    return Environment(
        loader=FileSystemLoader(str(_TEMPLATES_DIR)),
        autoescape=select_autoescape(enabled_extensions=()),
        trim_blocks=True,
        lstrip_blocks=True,
    )


def render_weekly_brief(context: WeeklyBriefContext | None = None) -> str:
    ctx = context or WeeklyBriefContext()
    template = _env().get_template("weekly-brief.md.j2")
    return template.render(
        report=ctx.report,
        key_conclusions=ctx.key_conclusions,
        target_dynamics=ctx.target_dynamics,
        asset_company_dynamics=ctx.asset_company_dynamics,
        trial_changes=ctx.trial_changes,
        publications_congress=ctx.publications_congress,
        competitive_landscape=ctx.competitive_landscape,
        indication_impact=ctx.indication_impact,
        watch_next_week=ctx.watch_next_week,
        evidence_uncertainties=ctx.evidence_uncertainties,
    )
