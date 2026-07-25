"""已审核文献摘要 — 导出到 Vault Dashboard。"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from apps.processor.publication_analysis import analyze_publication
from apps.reporter.review_queue import profiled_publication_relevance
from packages.domain.enums import EventType, MedicalReviewStatus
from packages.domain.models import Event, Evidence, Publication
from packages.obsidian_exporter.publication_context import resolve_publication_export_context
from packages.obsidian_exporter.vault_layout import ensure_vault_layout


def _resolve_publication(session: Session, event: Event, evidences: list[Evidence]) -> Publication | None:
    for evidence in evidences:
        if evidence.id.startswith("EVD-PM-"):
            pub = session.get(Publication, evidence.id.removeprefix("EVD-PM-"))
            if pub:
                return pub
    return session.scalar(select(Publication).where(Publication.title == event.title).limit(1))


def export_approved_publications_digest(
    session: Session,
    vault_root: Path,
    *,
    use_llm: bool = False,
) -> Path:
    ensure_vault_layout(vault_root)
    approved = list(
        session.scalars(
            select(Event)
            .where(
                Event.event_type == EventType.PUBLICATION,
                Event.medical_review_status == MedicalReviewStatus.APPROVED,
            )
            .order_by(Event.event_date.desc())
        ).all()
    )
    lines = [
        "# 已审核文献摘要",
        "",
        f"> 生成时间：{datetime.now(tz=UTC).isoformat(timespec='seconds')}",
        "",
    ]
    if not approved:
        lines.append("_暂无 approved 文献。请在 Obsidian 将过线文献 `review_status` 改为 `approved` 后 sync + publish。_")
    for event in approved:
        evidences = list(session.scalars(select(Evidence).where(Evidence.event_id == event.id)).all())
        ctx = resolve_publication_export_context(session, event, evidences)
        publication = _resolve_publication(session, event, evidences)
        rel = profiled_publication_relevance(session, event, evidences)
        lines.extend(
            [
                f"## {event.title}",
                "",
                f"- **event_id**：{event.id}",
                f"- **日期**：{event.event_date.isoformat()}",
                f"- **相关度**：{rel:.2f}",
            ]
        )
        if ctx and ctx.doi:
            lines.append(f"- **DOI**：[{ctx.doi}](https://doi.org/{ctx.doi})")
        if ctx and ctx.pmid:
            lines.append(f"- **PubMed**：https://pubmed.ncbi.nlm.nih.gov/{ctx.pmid}/")

        analysis_text = ctx.analysis_zh if ctx else None
        if not analysis_text and publication:
            study_type = "other"
            targets: list[str] = []
            if event.summary:
                import re

                m = re.search(r"study_type=([^;]+)", event.summary)
                if m:
                    study_type = m.group(1).strip()
                m2 = re.search(r"targets=([^;]+)", event.summary)
                if m2:
                    targets = [t.strip() for t in m2.group(1).split(",") if t.strip()]
            result, method = analyze_publication(
                title=publication.title,
                abstract=publication.abstract,
                doi=publication.doi,
                pmid=publication.pmid,
                study_type=study_type,
                matched_targets=targets,
                use_llm=use_llm,
            )
            analysis_text = (
                f"**{result.summary_zh}**\n\n"
                f"要点：{result.key_findings}\n\n"
                f"与 IL-4Rα：{result.il4ra_linkage}"
                f"（抽取={method}）"
            )
        lines.extend(["", "### 研判摘要", "", analysis_text or "_无摘要_", ""])
    dest = vault_root / "00-Dashboard" / "已审核文献摘要.md"
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return dest
