"""Obsidian Vault 目录规范 — 对齐 docs/reporting-style.md §5。"""

from __future__ import annotations

from pathlib import Path

from packages.domain.enums import EventType

VAULT_ROOT_NAME = "Target-Intelligence"

TOP_LEVEL_DIRS: tuple[str, ...] = (
    "00-Dashboard",
    "01-Targets",
    "02-Assets",
    "03-Companies",
    "04-Indications",
    "05-Trials",
    "06-Publications",
    "07-Events/Clinical",
    "07-Events/Financing",
    "07-Events/Congress",
    "07-Events/Regulatory",
    "07-Events/Other",
    "08-Daily-Briefs",
    "09-Weekly-Briefs",
    "10-Source-Documents",
    "99-Templates",
)

_EVENT_TYPE_DIRS: dict[EventType, str] = {
    EventType.CLINICAL_RESULT: "07-Events/Clinical",
    EventType.TRIAL_CHANGE: "07-Events/Clinical",
    EventType.DEAL: "07-Events/Financing",
    EventType.CONGRESS: "07-Events/Congress",
    EventType.REGULATORY: "07-Events/Regulatory",
    EventType.PUBLICATION: "06-Publications",
}


def event_relative_dir(event_type: EventType) -> str:
    return _EVENT_TYPE_DIRS.get(event_type, "07-Events/Other")


def ensure_vault_layout(vault_root: Path) -> None:
    """创建 Vault 顶层与子目录（幂等）。"""
    for rel in TOP_LEVEL_DIRS:
        (vault_root / rel).mkdir(parents=True, exist_ok=True)


def event_note_path(vault_root: Path, event_id: str, event_type: EventType) -> Path:
    rel_dir = event_relative_dir(event_type)
    safe_id = event_id.replace("/", "-")
    return vault_root / rel_dir / f"{safe_id}.md"


def weekly_note_path(vault_root: Path, report_id: str, period_start: str) -> Path:
    safe_id = report_id.replace("/", "-")
    return vault_root / "09-Weekly-Briefs" / f"{period_start}_{safe_id}.md"
