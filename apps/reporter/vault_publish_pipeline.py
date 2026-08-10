"""Vault 拉取 → review_sync → LLM publish 一键流水线。"""

from __future__ import annotations

import argparse
import os
import subprocess
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy.orm import Session

from apps.reporter.publish import publish_vault
from apps.reporter.review_sync import sync_review_status_from_vault


@dataclass
class VaultPipelineStats:
    vault_pulled: bool = False
    review_updated: int = 0
    skipped: bool = False
    events_exported: int = 0
    reports_exported: int = 0
    git_pushed: bool = False


def _resolve_vault_branch(vault_root: Path) -> str:
    for branch in ("master", "main"):
        probe = subprocess.run(
            ["git", "rev-parse", "--verify", f"origin/{branch}"],
            cwd=vault_root,
            capture_output=True,
            check=False,
        )
        if probe.returncode == 0:
            return branch
    current = subprocess.run(
        ["git", "rev-parse", "--abbrev-ref", "HEAD"],
        cwd=vault_root,
        capture_output=True,
        text=True,
        check=True,
    )
    return current.stdout.strip() or "master"


def pull_vault(vault_root: Path) -> bool:
    """从 origin 拉取 Vault；有更新返回 True。"""
    if not (vault_root / ".git").is_dir():
        return False
    before = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=vault_root,
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()
    subprocess.run(["git", "fetch", "origin"], cwd=vault_root, check=True, capture_output=True)
    branch = _resolve_vault_branch(vault_root)
    pull = subprocess.run(
        ["git", "pull", "--ff-only", "origin", branch],
        cwd=vault_root,
        capture_output=True,
        text=True,
        check=False,
    )
    if pull.returncode != 0:
        err = (pull.stderr or pull.stdout or "").strip()
        raise RuntimeError(f"vault git pull failed: {err}")
    after = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=vault_root,
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()
    return before != after


def publish_use_llm_default() -> bool:
    flag = os.getenv("PUBLISH_USE_LLM", "").strip().lower()
    if flag in ("1", "true", "yes", "on"):
        return True
    if flag in ("0", "false", "no", "off"):
        return False
    return bool(os.getenv("OPENAI_API_KEY"))


def run_vault_publish_pipeline(
    session: Session,
    vault_root: Path,
    *,
    pull: bool = True,
    force: bool = False,
    use_llm: bool | None = None,
    enrich_publications: bool = True,
    generate_weekly: bool = True,
    git_remote: str | None = None,
) -> VaultPipelineStats:
    """Obsidian 审阅 push 后，服务器侧完整闭环。"""
    stats = VaultPipelineStats()
    if pull:
        stats.vault_pulled = pull_vault(vault_root)
    sync_stats = sync_review_status_from_vault(session, vault_root)
    stats.review_updated = sync_stats.updated
    if not force and not stats.vault_pulled and sync_stats.updated == 0:
        stats.skipped = True
        return stats
    llm = publish_use_llm_default() if use_llm is None else use_llm
    pub = publish_vault(
        session,
        vault_root,
        generate_weekly=generate_weekly,
        git_remote=git_remote,
        use_llm=llm,
        enrich_publications=enrich_publications,
    )
    stats.events_exported = pub.events_exported
    stats.reports_exported = pub.reports_exported
    stats.git_pushed = pub.git_pushed
    return stats


def main() -> None:
    from packages.domain.database import SessionLocal
    from packages.domain.env import load_project_env

    load_project_env()
    parser = argparse.ArgumentParser(
        description="Pull Vault → review_sync → enrich + LLM publish → git push"
    )
    parser.add_argument("--vault", type=Path, default=Path(os.getenv("VAULT_PATH", "vault")))
    parser.add_argument("--no-pull", action="store_true", help="Skip git pull (vault already updated)")
    parser.add_argument("--force", action="store_true", help="Publish even if pull/sync made no changes")
    parser.add_argument("--no-weekly", action="store_true")
    parser.add_argument("--no-llm", action="store_true", help="Disable LLM even if OPENAI_API_KEY set")
    parser.add_argument("--no-enrich", action="store_true")
    args = parser.parse_args()

    session = SessionLocal()
    try:
        stats = run_vault_publish_pipeline(
            session,
            args.vault,
            pull=not args.no_pull,
            force=args.force,
            use_llm=False if args.no_llm else None,
            enrich_publications=not args.no_enrich,
            generate_weekly=not args.no_weekly,
            git_remote=os.getenv("VAULT_GIT_REMOTE"),
        )
        session.commit()
        if stats.skipped:
            print(
                "vault_pipeline: skipped (no vault pull changes, review_sync updated=0). "
                "Use --force to publish anyway."
            )
            return
        print(
            f"vault_pipeline: pulled={stats.vault_pulled} review_updated={stats.review_updated} "
            f"events={stats.events_exported} reports={stats.reports_exported} "
            f"git_pushed={stats.git_pushed} use_llm={publish_use_llm_default() and not args.no_llm}"
        )
    finally:
        session.close()


if __name__ == "__main__":
    main()
