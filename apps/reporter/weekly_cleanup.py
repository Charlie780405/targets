"""周报去重与空草稿清理。"""

from __future__ import annotations

import re
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from packages.domain.enums import ReportType
from packages.domain.models import Report
from packages.obsidian_exporter.exporter import parse_frontmatter


def is_empty_weekly_brief(body: str) -> bool:
    """无 approved 关键结论，且 §2–§7 无实质条目（仅「暂无」或单条弱相关）。"""
    if "本周暂无已审核" not in body:
        return False
    sections = re.split(r"^## \d+\.", body, flags=re.MULTILINE)
    substantive = 0
    for block in sections[1:8]:
        block = block.strip()
        if not block or block.startswith("_暂无"):
            continue
        lines = [
            ln
            for ln in block.splitlines()
            if ln.strip().startswith("- **") or ln.strip().startswith("- ")
        ]
        if lines:
            substantive += 1
    return substantive == 0


def canonical_weekly_report_ids(session: Session) -> set[str]:
    """每个周期保留最新一条周报 ID。"""
    reports = list(
        session.scalars(
            select(Report)
            .where(Report.report_type == ReportType.WEEKLY)
            .order_by(Report.generated_at.desc())
        ).all()
    )
    seen: set[tuple[str, str, str | None]] = set()
    keep: set[str] = set()
    for report in reports:
        key = (
            report.period_start.isoformat(),
            report.period_end.isoformat(),
            report.target_id,
        )
        if key in seen:
            continue
        seen.add(key)
        keep.add(report.id)
    return keep


def dedupe_weekly_reports_in_db(session: Session) -> int:
    """删除 DB 中同周期重复周报，保留最新一条。"""
    keep_ids = canonical_weekly_report_ids(session)
    removed = 0
    for report in list(session.scalars(select(Report).where(Report.report_type == ReportType.WEEKLY)).all()):
        if report.id not in keep_ids:
            session.delete(report)
            removed += 1
    session.flush()
    return removed


def prune_weekly_brief_files(
    vault_root: Path,
    *,
    keep_report_ids: set[str],
    remove_empty: bool = True,
) -> int:
    """删除 Vault 中多余或空的 09-Weekly-Briefs/*.md。"""
    brief_dir = vault_root / "09-Weekly-Briefs"
    if not brief_dir.is_dir():
        return 0
    pruned = 0
    for path in list(brief_dir.glob("*.md")):
        text = path.read_text(encoding="utf-8")
        fm = parse_frontmatter(text)
        report_id = str(fm.get("report_id") or "")
        body = text.split("---", 2)[-1] if text.startswith("---") else text
        should_remove = report_id not in keep_report_ids
        if not should_remove and remove_empty and is_empty_weekly_brief(body):
            should_remove = True
        if should_remove:
            path.unlink(missing_ok=True)
            pruned += 1
    return pruned


def remove_empty_weekly_reports_from_db(session: Session) -> int:
    """删除 DB 中无实质内容的周报。"""
    removed = 0
    for report in list(session.scalars(select(Report).where(Report.report_type == ReportType.WEEKLY)).all()):
        if is_empty_weekly_brief(report.body_markdown):
            session.delete(report)
            removed += 1
    session.flush()
    return removed


def cleanup_weekly_briefs(session: Session, vault_root: Path) -> dict[str, int]:
    """DB 去重 + 删空草稿 + Vault prune。"""
    deduped = dedupe_weekly_reports_in_db(session)
    empty_removed = remove_empty_weekly_reports_from_db(session)
    keep_ids = {
        r.id
        for r in session.scalars(select(Report).where(Report.report_type == ReportType.WEEKLY)).all()
    }
    vault_pruned = prune_weekly_brief_files(vault_root, keep_report_ids=keep_ids)
    return {
        "db_removed": deduped + empty_removed,
        "vault_pruned": vault_pruned,
        "keep_count": len(keep_ids),
    }


def main() -> None:
    import argparse

    from packages.domain.database import SessionLocal
    from packages.domain.env import load_project_env

    load_project_env()
    parser = argparse.ArgumentParser(description="Dedupe DB weekly reports and prune empty Vault briefs")
    parser.add_argument("--vault", type=Path, default=Path("vault"))
    args = parser.parse_args()
    session = SessionLocal()
    try:
        result = cleanup_weekly_briefs(session, args.vault)
        session.commit()
        print(
            f"weekly_cleanup: db_removed={result['db_removed']} "
            f"vault_pruned={result['vault_pruned']} keep={result['keep_count']}"
        )
    finally:
        session.close()


if __name__ == "__main__":
    main()
