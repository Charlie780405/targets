"""导出事件/周报到 Vault 并 Git 同步。"""

from __future__ import annotations

import os
import subprocess
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from apps.processor.publication_relevance import load_publication_filter_config
from apps.processor.scoring import significance_label
from apps.processor.target_link import backfill_event_target_ids
from apps.reporter.dashboard import export_pending_review_dashboard
from apps.reporter.weekly import default_week_window, save_weekly_report
from packages.domain.enums import MedicalReviewStatus
from packages.domain.models import Asset, Event, Evidence, Indication, Organization, Report, Target
from packages.obsidian_exporter.exporter import (
    EntityLabels,
    export_event_note,
    export_publication_template,
    export_report_note,
)


@dataclass
class PublishStats:
    events_exported: int = 0
    reports_exported: int = 0
    git_pushed: bool = False
    events_skipped: int = 0


def _importance_band(significance: float | None) -> str:
    score = significance or 0.0
    label = significance_label(score)
    return {"高": "high", "中": "medium", "低": "low"}.get(label, "low")


def _passes_export_filter(event: Event, min_importance: str | None) -> bool:
    if event.medical_review_status == MedicalReviewStatus.REJECTED:
        return False
    if not min_importance:
        return True
    order = {"low": 0, "medium": 1, "high": 2}
    band = _importance_band(event.significance_score)
    return order.get(band, 0) >= order.get(min_importance, 0)


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


def export_events(
    session: Session,
    vault_root: Path,
    *,
    since_id: str | None = None,
    min_importance: str | None = None,
) -> tuple[int, int]:
    stmt = select(Event).order_by(Event.event_date.desc())
    if since_id:
        stmt = stmt.where(Event.id >= since_id)
    events = list(session.scalars(stmt).all())
    exported = 0
    skipped = 0
    for event in events:
        if not _passes_export_filter(event, min_importance):
            skipped += 1
            continue
        evidences = list(session.scalars(select(Evidence).where(Evidence.event_id == event.id)).all())
        export_event_note(
            event,
            evidences,
            vault_root,
            labels=_labels_for_event(session, event),
            session=session,
        )
        exported += 1
    return exported, skipped


def export_reports(session: Session, vault_root: Path) -> int:
    reports = list(session.scalars(select(Report).order_by(Report.generated_at.desc())).all())
    seen_periods: set[tuple[str, str, str | None]] = set()
    count = 0
    for report in reports:
        key = (
            report.period_start.isoformat(),
            report.period_end.isoformat(),
            report.target_id,
        )
        if key in seen_periods:
            continue
        seen_periods.add(key)
        target = session.get(Target, report.target_id) if report.target_id else None
        export_report_note(report, vault_root, target_name=target.canonical_name if target else None)
        count += 1
    return count


def _ensure_vault_git_identity(vault_root: Path) -> None:
    """Vault 独立仓库首次 commit 需本地 identity（不修改 global git config）。"""
    email = subprocess.run(
        ["git", "config", "user.email"],
        cwd=vault_root,
        capture_output=True,
        text=True,
        check=False,
    )
    if email.stdout.strip():
        return
    name = os.getenv("VAULT_GIT_USER_NAME", "target-intelligence")
    mail = os.getenv("VAULT_GIT_USER_EMAIL", "Charlie780405@outlook.com")
    subprocess.run(["git", "config", "user.name", name], cwd=vault_root, check=True)
    subprocess.run(["git", "config", "user.email", mail], cwd=vault_root, check=True)


def git_sync_vault(vault_root: Path, *, remote: str | None = None, message: str = "sync vault") -> bool:
    """在 Vault 目录 git add/commit/push；无 remote 时仅 commit。"""
    if not (vault_root / ".git").exists():
        subprocess.run(["git", "init"], cwd=vault_root, check=True, capture_output=True)
    _ensure_vault_git_identity(vault_root)
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
    commit = subprocess.run(
        ["git", "commit", "-m", message],
        cwd=vault_root,
        capture_output=True,
        text=True,
        check=False,
    )
    if commit.returncode != 0:
        err = (commit.stderr or commit.stdout or "").strip()
        raise RuntimeError(f"vault git commit failed: {err}")
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
    push = subprocess.run(
        ["git", "push", "-u", "origin", "HEAD"],
        cwd=vault_root,
        capture_output=True,
        text=True,
        check=False,
    )
    if push.returncode != 0:
        err = (push.stderr or push.stdout or "").strip()
        import sys

        print(f"WARN vault git push failed: {err}", file=sys.stderr)
        if git_remote.startswith("https://"):
            print(
                "HINT: 服务器请改用 SSH remote，例如 "
                "git@github.com:Charlie780405/target-intel-vault.git",
                file=sys.stderr,
            )
        return False
    return True


def publish_vault(
    session: Session,
    vault_root: Path,
    *,
    generate_weekly: bool = True,
    git_remote: str | None = None,
    use_llm: bool = False,
    enrich_publications: bool = False,
    min_importance: str | None = None,
) -> PublishStats:
    stats = PublishStats()
    if enrich_publications:
        from apps.collector.run_publication_enrich import enrich_publication_events

        enrich_publication_events(session, use_llm=use_llm)
    if generate_weekly:
        backfill_event_target_ids(session)
        start, end = default_week_window()
        save_weekly_report(session, start, end, use_llm=use_llm)
        session.commit()
    filt = load_publication_filter_config()
    export_min = min_importance or str(filt.get("export_min_importance") or "medium")
    exported, skipped = export_events(session, vault_root, min_importance=export_min)
    stats.events_exported = exported
    stats.events_skipped = skipped
    stats.reports_exported = export_reports(session, vault_root)
    export_pending_review_dashboard(session, vault_root)
    export_publication_template(vault_root)
    stats.git_pushed = git_sync_vault(vault_root, remote=git_remote)
    return stats


def main() -> None:
    import argparse

    from packages.domain.env import load_project_env

    load_project_env()

    parser = argparse.ArgumentParser(description="Export events/reports to Obsidian Vault and git sync")
    parser.add_argument("--vault", type=Path, default=Path(os.getenv("VAULT_PATH", "vault")))
    parser.add_argument("--no-weekly", action="store_true", help="Skip weekly report generation")
    parser.add_argument("--use-llm", action="store_true")
    parser.add_argument("--enrich-publications", action="store_true")
    parser.add_argument(
        "--min-importance",
        choices=["low", "medium", "high"],
        default=None,
        help="Override export_min_importance from config",
    )
    args = parser.parse_args()

    from packages.domain.database import SessionLocal

    session = SessionLocal()
    try:
        stats = publish_vault(
            session,
            args.vault,
            generate_weekly=not args.no_weekly,
            use_llm=args.use_llm,
            enrich_publications=args.enrich_publications,
            min_importance=args.min_importance,
        )
        session.commit()
        print(
            f"publish: events={stats.events_exported} skipped={stats.events_skipped} "
            f"reports={stats.reports_exported} git_pushed={stats.git_pushed}"
        )
    finally:
        session.close()


if __name__ == "__main__":
    main()
