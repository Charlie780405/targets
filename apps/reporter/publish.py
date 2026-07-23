"""导出事件/周报到 Vault 并 Git 同步。"""

from __future__ import annotations

import os
import subprocess
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from apps.reporter.weekly import default_week_window, save_weekly_report
from packages.domain.models import Asset, Event, Evidence, Indication, Organization, Report, Target
from packages.obsidian_exporter.exporter import EntityLabels, export_event_note, export_report_note


@dataclass
class PublishStats:
    events_exported: int = 0
    reports_exported: int = 0
    git_pushed: bool = False


def _labels_for_event(session: Session, event: Event) -> EntityLabels:
    target = session.get(Target, event.target_id) if event.target_id else None
    asset = session.get(Asset, event.asset_id) if event.asset_id else None
    indication = session.get(Indication, event.indication_id) if event.indication_id else None
    org = session.get(Organization, event.organization_id) if event.organization_id else None
    asset_label = asset.inn or asset.brand or asset.id if asset else None
    return EntityLabels(
        target=target.canonical_name if target else None,
        asset=asset_label,
        indication=indication.canonical_name if indication else None,
        organization=org.canonical_name if org else None,
    )


def export_events(session: Session, vault_root: Path, *, since_id: str | None = None) -> int:
    stmt = select(Event).order_by(Event.event_date.desc())
    if since_id:
        stmt = stmt.where(Event.id >= since_id)
    events = list(session.scalars(stmt).all())
    count = 0
    for event in events:
        evidences = list(session.scalars(select(Evidence).where(Evidence.event_id == event.id)).all())
        export_event_note(event, evidences, vault_root, labels=_labels_for_event(session, event))
        count += 1
    return count


def export_reports(session: Session, vault_root: Path) -> int:
    reports = list(session.scalars(select(Report).order_by(Report.generated_at.desc())).all())
    count = 0
    for report in reports:
        target = session.get(Target, report.target_id) if report.target_id else None
        export_report_note(report, vault_root, target_name=target.canonical_name if target else None)
        count += 1
    return count


def git_sync_vault(vault_root: Path, *, remote: str | None = None, message: str = "sync vault") -> bool:
    """在 Vault 目录 git add/commit/push；无 remote 时仅 commit。"""
    if not (vault_root / ".git").exists():
        subprocess.run(["git", "init"], cwd=vault_root, check=True, capture_output=True)
    subprocess.run(["git", "add", "-A"], cwd=vault_root, check=True, capture_output=True)
    status = subprocess.run(
        ["git", "status", "--porcelain"],
        cwd=vault_root,
        check=True,
        capture_output=True,
        text=True,
    )
    if not status.stdout.strip():
        return False
    subprocess.run(["git", "commit", "-m", message], cwd=vault_root, check=True, capture_output=True)
    git_remote = remote or os.getenv("VAULT_GIT_REMOTE")
    if not git_remote:
        return False
    remotes = subprocess.run(
        ["git", "remote"],
        cwd=vault_root,
        check=True,
        capture_output=True,
        text=True,
    )
    if "origin" in remotes.stdout.split():
        subprocess.run(["git", "remote", "set-url", "origin", git_remote], cwd=vault_root, check=True)
    else:
        subprocess.run(["git", "remote", "add", "origin", git_remote], cwd=vault_root, check=True)
    subprocess.run(["git", "push", "-u", "origin", "HEAD"], cwd=vault_root, check=True, capture_output=True)
    return True


def publish_vault(
    session: Session,
    vault_root: Path,
    *,
    generate_weekly: bool = True,
    git_remote: str | None = None,
    use_llm: bool = False,
) -> PublishStats:
    stats = PublishStats()
    if generate_weekly:
        start, end = default_week_window()
        save_weekly_report(session, start, end, use_llm=use_llm)
        session.commit()
    stats.events_exported = export_events(session, vault_root)
    stats.reports_exported = export_reports(session, vault_root)
    stats.git_pushed = git_sync_vault(vault_root, remote=git_remote)
    return stats


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Export events/reports to Obsidian Vault and git sync")
    parser.add_argument("--vault", type=Path, default=Path(os.getenv("VAULT_PATH", "vault")))
    parser.add_argument("--no-weekly", action="store_true", help="Skip weekly report generation")
    parser.add_argument("--use-llm", action="store_true")
    args = parser.parse_args()

    from packages.domain.database import SessionLocal

    session = SessionLocal()
    try:
        stats = publish_vault(
            session,
            args.vault,
            generate_weekly=not args.no_weekly,
            use_llm=args.use_llm,
        )
        session.commit()
        print(
            f"publish: events={stats.events_exported} reports={stats.reports_exported} "
            f"git_pushed={stats.git_pushed}"
        )
    finally:
        session.close()


if __name__ == "__main__":
    main()
