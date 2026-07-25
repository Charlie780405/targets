"""事件与 config/targets 靶点 ID 关联。"""

from __future__ import annotations

import re

from sqlalchemy import select
from sqlalchemy.orm import Session

from packages.domain.models import Event
from packages.entity_resolution.target_dictionary import TargetDictionary

_TARGET_SUMMARY_RE = re.compile(r"targets=([^;]+)")


def resolve_target_id_from_matches(
    matched_targets: list[str],
    *,
    target_dictionary: TargetDictionary | None = None,
) -> str | None:
    dictionary = target_dictionary or TargetDictionary.from_config_dir()
    by_name = {entry.canonical_name: entry.target_id for entry in dictionary.all_entries()}
    for name in matched_targets:
        target_id = by_name.get(name)
        if target_id:
            return target_id
    return None


def backfill_event_target_ids(session: Session) -> int:
    """从 summary 中的 targets= 回填缺失的 target_id。"""
    dictionary = TargetDictionary.from_config_dir()
    by_name = {entry.canonical_name: entry.target_id for entry in dictionary.all_entries()}
    updated = 0
    for event in session.scalars(select(Event).where(Event.target_id.is_(None))):
        if not event.summary:
            continue
        match = _TARGET_SUMMARY_RE.search(event.summary)
        if not match:
            continue
        for name in match.group(1).split(","):
            target_id = by_name.get(name.strip())
            if target_id:
                event.target_id = target_id
                updated += 1
                break
    if updated:
        session.flush()
    return updated
