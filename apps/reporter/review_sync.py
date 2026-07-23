"""从 Obsidian Vault frontmatter 回写 medical_review_status 到 DB（SSOT）。"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from sqlalchemy.orm import Session

from packages.domain.enums import MedicalReviewStatus
from packages.domain.models import Event
from packages.obsidian_exporter.exporter import parse_frontmatter
from packages.obsidian_exporter.vault_layout import TOP_LEVEL_DIRS

_VALID_STATUSES = {s.value for s in MedicalReviewStatus}


@dataclass
class ReviewSyncStats:
    scanned: int = 0
    updated: int = 0
    skipped: int = 0


def _iter_vault_markdown(vault_root: Path) -> list[Path]:
    files: list[Path] = []
    for rel in TOP_LEVEL_DIRS:
        dir_path = vault_root / rel
        if dir_path.is_dir():
            files.extend(dir_path.rglob("*.md"))
    return files


def sync_review_status_from_vault(session: Session, vault_root: Path) -> ReviewSyncStats:
    stats = ReviewSyncStats()
    for path in _iter_vault_markdown(vault_root):
        stats.scanned += 1
        text = path.read_text(encoding="utf-8")
        fm = parse_frontmatter(text)
        event_id = fm.get("event_id")
        review_status = fm.get("review_status")
        if not event_id or not review_status:
            stats.skipped += 1
            continue
        status_str = str(review_status).lower()
        if status_str not in _VALID_STATUSES:
            stats.skipped += 1
            continue
        event = session.get(Event, str(event_id))
        if event is None:
            stats.skipped += 1
            continue
        new_status = MedicalReviewStatus(status_str)
        if event.medical_review_status != new_status:
            event.medical_review_status = new_status
            stats.updated += 1
    session.flush()
    return stats
