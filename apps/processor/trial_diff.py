"""试验快照字段 diff → trial_change 事件。"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime
from typing import Any

from packages.domain.content_hash import compute_content_hash
from packages.domain.enums import EventType, MedicalReviewStatus
from packages.domain.models import Event, Trial, TrialSnapshot
from packages.source_adapters.clinicaltrials.parser import WATCH_FIELD_KEYS

# Enrollment 小幅修订阈值（|Δ| ≤ 此值视为噪声，不生成事件）
ENROLLMENT_NOISE_THRESHOLD = 5


@dataclass(frozen=True)
class FieldChange:
    field: str
    old_value: Any
    new_value: Any


def diff_watch_fields(
    old_fields: dict[str, Any],
    new_fields: dict[str, Any],
    *,
    watch_keys: tuple[str, ...] = WATCH_FIELD_KEYS,
) -> list[FieldChange]:
    changes: list[FieldChange] = []
    for key in watch_keys:
        old_val = old_fields.get(key)
        new_val = new_fields.get(key)
        if old_val != new_val:
            changes.append(FieldChange(field=key, old_value=old_val, new_value=new_val))
    return changes


def is_medically_meaningful_change(changes: list[FieldChange]) -> bool:
    """过滤无医学意义的噪声更新（如 enrollment 小幅修订）。"""
    if not changes:
        return False
    if len(changes) == 1 and changes[0].field == "EnrollmentCount":
        try:
            old = int(changes[0].old_value or 0)
            new = int(changes[0].new_value or 0)
            if abs(new - old) <= ENROLLMENT_NOISE_THRESHOLD:
                return False
        except (TypeError, ValueError):
            pass
    return True


def format_change_summary(changes: list[FieldChange]) -> str:
    parts = [f"{c.field}: {c.old_value!r} → {c.new_value!r}" for c in changes]
    return "; ".join(parts)


def build_trial_change_event(
    trial: Trial,
    changes: list[FieldChange],
    *,
    event_id: str,
    event_date: date | None = None,
) -> Event:
    summary = format_change_summary(changes)
    title = f"Trial {trial.nct_id or trial.id} status change: {changes[0].field}"
    payload = {
        "trial_id": trial.id,
        "nct_id": trial.nct_id,
        "changes": [{"field": c.field, "old": c.old_value, "new": c.new_value} for c in changes],
    }
    return Event(
        id=event_id,
        event_type=EventType.TRIAL_CHANGE,
        target_id=trial.target_id,
        asset_id=trial.asset_id,
        indication_id=trial.indication_id,
        organization_id=trial.sponsor_org_id,
        event_date=event_date or datetime.now(tz=UTC).date(),
        discovered_at=datetime.now(tz=UTC),
        title=title,
        summary=summary,
        medical_review_status=MedicalReviewStatus.PENDING,
        source_count=1,
        content_hash=compute_content_hash(payload),
    )


def diff_snapshots(
    previous: TrialSnapshot | None,
    current_watch_fields: dict[str, Any],
) -> list[FieldChange]:
    if previous is None or previous.payload_json is None:
        return []
    old_fields = previous.payload_json
    return diff_watch_fields(old_fields, current_watch_fields)
