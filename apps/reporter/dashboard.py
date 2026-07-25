"""导出 Vault Dashboard — 待审队列与指标。"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from apps.processor.metrics import compute_metrics, format_metrics_markdown
from apps.reporter.review_queue import profiled_publication_relevance, select_review_queue_event_ids
from apps.reporter.weekly import default_week_window
from packages.domain.enums import EventType, MedicalReviewStatus
from packages.domain.models import Event, Evidence
from packages.obsidian_exporter.vault_layout import ensure_vault_layout


def export_pending_review_dashboard(session: Session, vault_root: Path) -> Path:
    ensure_vault_layout(vault_root)
    queue_ids = select_review_queue_event_ids(session)
    pending = list(
        session.scalars(
            select(Event)
            .where(Event.medical_review_status == MedicalReviewStatus.PENDING)
            .order_by(Event.event_date.desc())
        ).all()
    )
    pub_rows: list[tuple[Event, float]] = []
    for event in pending:
        if event.event_type != EventType.PUBLICATION or event.id not in queue_ids:
            continue
        evidences = list(
            session.scalars(select(Evidence).where(Evidence.event_id == event.id)).all()
        )
        rel = profiled_publication_relevance(session, event, evidences)
        pub_rows.append((event, rel))
    pub_rows.sort(key=lambda x: (-x[1], x[0].event_date.isoformat()))

    start, end = default_week_window()
    metrics = compute_metrics(session, start, end)
    lines = [
        "# 待审队列",
        "",
        f"> 生成时间：{datetime.now(tz=UTC).isoformat(timespec='seconds')}",
        f"> 文献审核队列 Top **{len(pub_rows)}** 篇（按 IL-4Rα 管线相关度）",
        "",
        "## 指标快照",
        "",
        format_metrics_markdown(metrics),
        "",
        "## 待审文献（Vault 将导出）",
        "",
        "| event_id | 相关度 | 日期 | 标题 |",
        "| --- | --- | --- | --- |",
    ]
    if not pub_rows:
        lines.append("| — | — | — | _队列为空_ |")
    for event, rel in pub_rows:
        title = event.title.replace("|", "\\|")[:80]
        link = f"[{event.id}](06-Publications/{event.id}.md)"
        lines.append(
            f"| {link} | {rel:.2f} | {event.event_date.isoformat()} | {title} |"
        )
    lines.extend(
        [
            "",
            "## 审核说明",
            "",
            "1. 打开 `06-Publications/` 中笔记，阅读 **摘要（原文）** 与 **研判草稿**",
            "2. 修改 frontmatter `review_status`：`approved`（保留并纳入摘要）/ `rejected`（移出 Vault）",
            "3. 本地保存后：`python3 -m apps.reporter.review_sync --vault ./vault`",
            "4. 服务器：`python3 -m apps.reporter.publish --vault ./vault --enrich-publications --use-llm`",
            "5. 已 approved 文献见 `00-Dashboard/已审核文献摘要.md`",
        ]
    )
    dest = vault_root / "00-Dashboard" / "待审队列.md"
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return dest
