"""Event / Report → Obsidian Markdown（frontmatter SSOT 对齐 docs/event-schema.md §6）。"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml  # type: ignore[import-untyped]

from apps.processor.scoring import significance_label
from packages.domain.enums import EventType, MedicalReviewStatus
from packages.domain.models import Event, Evidence, Report
from packages.obsidian_exporter.vault_layout import (
    ensure_vault_layout,
    event_note_path,
    weekly_note_path,
)


@dataclass(frozen=True)
class EntityLabels:
    target: str | None = None
    asset: str | None = None
    indication: str | None = None
    organization: str | None = None


def _importance_band(significance: float | None) -> str:
    score = significance or 0.0
    label = significance_label(score)
    return {"高": "high", "中": "medium", "低": "low"}.get(label, "low")


def build_event_frontmatter(
    event: Event,
    evidences: list[Evidence],
    labels: EntityLabels | None = None,
) -> dict[str, Any]:
    lbl = labels or EntityLabels()
    sources = sorted({ev.source_name for ev in evidences})
    et = event.event_type.value if isinstance(event.event_type, EventType) else str(event.event_type)
    rs = event.medical_review_status
    review = rs.value if isinstance(rs, MedicalReviewStatus) else str(rs)
    fm: dict[str, Any] = {
        "event_id": event.id,
        "event_type": et,
        "event_date": event.event_date.isoformat(),
        "importance": _importance_band(event.significance_score),
        "confidence": round(event.confidence_score or 0.0, 2),
        "novelty": round(event.novelty_score or 0.0, 2),
        "review_status": review,
        "sources": sources,
    }
    if lbl.target:
        fm["target"] = lbl.target
    if lbl.asset:
        fm["asset"] = lbl.asset
    if lbl.indication:
        fm["indication"] = lbl.indication
    if lbl.organization:
        fm["organization"] = lbl.organization
    return fm


def build_report_frontmatter(report: Report, target_name: str | None = None) -> dict[str, Any]:
    rt = report.report_type.value if hasattr(report.report_type, "value") else str(report.report_type)
    fm: dict[str, Any] = {
        "report_id": report.id,
        "report_type": rt,
        "period_start": report.period_start.isoformat(),
        "period_end": report.period_end.isoformat(),
        "generated_at": report.generated_at.isoformat() if report.generated_at else None,
    }
    if target_name:
        fm["target"] = target_name
    return fm


def render_markdown_with_frontmatter(frontmatter: dict[str, Any], body: str) -> str:
    yaml_block = yaml.safe_dump(frontmatter, allow_unicode=True, sort_keys=False).strip()
    body_stripped = body.strip()
    return f"---\n{yaml_block}\n---\n\n{body_stripped}\n"


def export_event_note(
    event: Event,
    evidences: list[Evidence],
    vault_root: Path,
    *,
    labels: EntityLabels | None = None,
) -> Path:
    ensure_vault_layout(vault_root)
    frontmatter = build_event_frontmatter(event, evidences, labels)
    snippets = [ev.evidence_snippet for ev in evidences if ev.evidence_snippet]
    body_lines = [
        f"# {event.title}",
        "",
        event.summary or "_无摘要_",
        "",
        "## 证据片段",
        "",
    ]
    if snippets:
        for i, snippet in enumerate(snippets, 1):
            body_lines.append(f"{i}. {snippet}")
    else:
        body_lines.append("_无证据片段_")
    body_lines.extend(["", "## 来源链接", ""])
    for ev in evidences:
        body_lines.append(f"- [{ev.source_name}]({ev.source_url})")
    content = render_markdown_with_frontmatter(frontmatter, "\n".join(body_lines))
    dest = event_note_path(vault_root, event.id, event.event_type)
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(content, encoding="utf-8")
    return dest


def export_report_note(
    report: Report,
    vault_root: Path,
    *,
    target_name: str | None = None,
) -> Path:
    ensure_vault_layout(vault_root)
    frontmatter = build_report_frontmatter(report, target_name)
    content = render_markdown_with_frontmatter(frontmatter, report.body_markdown)
    dest = weekly_note_path(vault_root, report.id, report.period_start.isoformat())
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(content, encoding="utf-8")
    return dest


def parse_frontmatter(markdown: str) -> dict[str, Any]:
    """从 Markdown 文件解析 YAML frontmatter。"""
    if not markdown.startswith("---"):
        return {}
    parts = markdown.split("---", 2)
    if len(parts) < 3:
        return {}
    raw = yaml.safe_load(parts[1])
    return raw if isinstance(raw, dict) else {}
