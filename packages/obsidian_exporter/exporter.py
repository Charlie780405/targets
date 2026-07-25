"""Event / Report → Obsidian Markdown（frontmatter SSOT 对齐 docs/event-schema.md §6）。"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml  # type: ignore[import-untyped]
from sqlalchemy.orm import Session

from apps.processor.scoring import significance_label
from packages.domain.enums import EventType, MedicalReviewStatus
from packages.domain.models import Event, Evidence, Report
from packages.obsidian_exporter.publication_context import (
    PublicationExportContext,
    resolve_publication_export_context,
)
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
    publication: PublicationExportContext | None = None,
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
    if publication:
        if publication.pmid:
            fm["pmid"] = publication.pmid
        if publication.doi:
            fm["doi"] = publication.doi
        if publication.study_type:
            fm["study_type"] = publication.study_type
        if publication.published_at:
            fm["published_at"] = publication.published_at
        if publication.retracted:
            fm["retracted"] = True
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


def _build_publication_body(
    event: Event,
    evidences: list[Evidence],
    publication: PublicationExportContext | None,
) -> list[str]:
    lines = [f"# {event.title}", ""]
    if publication and publication.retracted:
        lines.extend(["> **RETRACTED**", ""])

    lines.extend(["## 机器标签", "", event.summary or "_无_", ""])

    if publication and publication.analysis_zh:
        lines.extend(["## 研判草稿（待审核）", "", publication.analysis_zh, ""])

    if publication and publication.abstract:
        lines.extend(["## 摘要（原文）", "", publication.abstract, ""])
    elif evidences and evidences[0].evidence_snippet:
        lines.extend(["## 证据片段", "", evidences[0].evidence_snippet, ""])

    lines.extend(["## 链接", ""])
    if publication and publication.pubmed_url:
        lines.append(f"- [PubMed]({publication.pubmed_url})")
    if publication and publication.doi_url:
        lines.append(f"- [DOI]({publication.doi_url})")
    for ev in evidences:
        if ev.source_url and (not publication or ev.source_url != publication.pubmed_url):
            lines.append(f"- [{ev.source_name}]({ev.source_url})")
    if len(lines) == lines.index("## 链接", 0) + 2:
        lines.append("_无链接_")

    if publication and publication.matched_targets:
        lines.extend(["", "## 匹配靶点", "", ", ".join(publication.matched_targets)])

    return lines


def export_event_note(
    event: Event,
    evidences: list[Evidence],
    vault_root: Path,
    *,
    labels: EntityLabels | None = None,
    session: Session | None = None,
) -> Path:
    ensure_vault_layout(vault_root)
    publication: PublicationExportContext | None = None
    if session is not None and event.event_type == EventType.PUBLICATION:
        publication = resolve_publication_export_context(session, event, evidences)

    frontmatter = build_event_frontmatter(event, evidences, labels, publication)

    if event.event_type == EventType.PUBLICATION:
        body_lines = _build_publication_body(event, evidences, publication)
    else:
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


def export_publication_template(vault_root: Path) -> Path:
    ensure_vault_layout(vault_root)
    template = vault_root / "99-Templates" / "publication-event.md"
    if not template.exists():
        template.write_text(
            "---\n"
            "event_id: EVT-YYYY-NNNNN\n"
            "event_type: publication\n"
            "review_status: pending\n"
            "pmid:\n"
            "doi:\n"
            "---\n\n"
            "# 标题\n\n"
            "## 机器标签\n\n"
            "## 研判草稿（待审核）\n\n"
            "## 摘要（原文）\n\n"
            "## 链接\n\n"
            "- [PubMed](https://pubmed.ncbi.nlm.nih.gov/)\n"
            "- [DOI](https://doi.org/)\n",
            encoding="utf-8",
        )
    return template


def parse_frontmatter(markdown: str) -> dict[str, Any]:
    """从 Markdown 文件解析 YAML frontmatter。"""
    if not markdown.startswith("---"):
        return {}
    parts = markdown.split("---", 2)
    if len(parts) < 3:
        return {}
    raw = yaml.safe_load(parts[1])
    return raw if isinstance(raw, dict) else {}
