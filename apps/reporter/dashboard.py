"""导出 Vault Dashboard — 待审队列与指标。"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from apps.processor.metrics import compute_metrics, format_metrics_markdown
from apps.processor.scoring import significance_label
from apps.reporter.weekly import default_week_window
from packages.domain.enums import EventType, MedicalReviewStatus
from packages.domain.models import Event
from packages.obsidian_exporter.vault_layout import ensure_vault_layout


def _importance_band(significance: float | None) -> str:
    score = significance or 0.0
    label = significance_label(score)
    return {"高": "high", "中": "medium", "低": "low"}.get(label, "low")


def export_pending_review_dashboard(session: Session, vault_root: Path) -> Path:
    ensure_vault_layout(vault_root)
    pending = list(
        session.scalars(
            select(Event)
            .where(Event.medical_review_status == MedicalReviewStatus.PENDING)
            .order_by(Event.significance_score.desc().nullslast(), Event.event_date.desc())
        ).all()
    )
    start, end = default_week_window()
    metrics = compute_metrics(session, start, end)
    lines = [
        "# 待审队列",
        "",
        f"> 生成时间：{datetime.now(tz=UTC).isoformat(timespec='seconds')}",
        "",
        "## 指标快照",
        "",
        format_metrics_markdown(metrics),
        "",
        "## 待审事件（按显著性）",
        "",
        "| event_id | 类型 | 日期 | 显著性 | 标题 |",
        "| --- | --- | --- | --- | --- |",
    ]
    for event in pending[:100]:
        et = event.event_type.value if isinstance(event.event_type, EventType) else str(event.event_type)
        band = _importance_band(event.significance_score)
        title = event.title.replace("|", "\\|")[:80]
        rel_dir = "06-Publications" if event.event_type == EventType.PUBLICATION else "07-Events"
        link = f"[[{rel_dir}/{event.id}|{event.id}]]"
        lines.append(
            f"| {link} | {et} | {event.event_date.isoformat()} | {band} | {title} |"
        )
    if not pending:
        lines.append("| — | — | — | — | _暂无待审_ |")
    lines.extend(
        [
            "",
            "## 审核说明",
            "",
            "1. 打开事件笔记，修改 frontmatter `review_status` 为 `approved` / `rejected` / `needs_info`",
            "2. 服务器执行：`python3 -m apps.reporter.review_sync --vault ./vault`",
            "3. 再执行：`python3 -m apps.reporter.publish --vault ./vault`",
        ]
    )
    dest = vault_root / "00-Dashboard" / "待审队列.md"
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return dest
