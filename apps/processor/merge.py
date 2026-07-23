"""跨来源事件合并 — 键 = 靶点+资产+适应症+event_type + 日期窗口。"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

from apps.processor.scoring import load_scoring_config
from packages.domain.models import Event, Evidence


@dataclass
class MergedEventGroup:
    """合并后的事件组：primary 代表组，members 含被合并的重复事件。"""

    primary: Event
    members: list[Event] = field(default_factory=list)
    evidences: list[Evidence] = field(default_factory=list)

    @property
    def all_events(self) -> list[Event]:
        return [self.primary, *self.members]

    @property
    def source_count(self) -> int:
        return len({ev.source_url for ev in self.evidences})


def merge_key(event: Event) -> tuple[str | None, str | None, str | None, str]:
    """(target_id, asset_id, indication_id, event_type) — 不含日期。"""
    et = event.event_type.value if hasattr(event.event_type, "value") else str(event.event_type)
    return (event.target_id, event.asset_id, event.indication_id, et)


def _dates_within_window(d1: date, d2: date, window_days: int) -> bool:
    return abs((d1 - d2).days) <= window_days


def _pick_primary(events: list[Event]) -> Event:
    """选 significance 最高者；并列取 event_date 最新。"""

    def sort_key(ev: Event) -> tuple[float, str]:
        sig = ev.significance_score or 0.0
        return (sig, ev.event_date.isoformat())

    return max(events, key=sort_key)


def merge_events(
    events: list[Event],
    *,
    window_days: int | None = None,
) -> list[MergedEventGroup]:
    """将同一读出/同一进展的多源事件合并为一组。"""
    if not events:
        return []

    cfg = load_scoring_config()
    window = window_days if window_days is not None else int(cfg["merge"]["date_window_days"])

    sorted_events = sorted(events, key=lambda e: (e.event_date, e.id))
    groups: list[list[Event]] = []

    for event in sorted_events:
        key = merge_key(event)
        placed = False
        for bucket in groups:
            if merge_key(bucket[0]) != key:
                continue
            if any(_dates_within_window(event.event_date, member.event_date, window) for member in bucket):
                bucket.append(event)
                placed = True
                break
        if not placed:
            groups.append([event])

    result: list[MergedEventGroup] = []
    for bucket in groups:
        primary = _pick_primary(bucket)
        members = [e for e in bucket if e.id != primary.id]
        result.append(MergedEventGroup(primary=primary, members=members))
    return result


def attach_evidences(
    groups: list[MergedEventGroup],
    evidences_by_event: dict[str, list[Evidence]],
) -> list[MergedEventGroup]:
    """把各成员事件的 Evidence 挂到合并组。"""
    for group in groups:
        seen_urls: set[str] = set()
        merged: list[Evidence] = []
        for ev in group.all_events:
            for evidence in evidences_by_event.get(ev.id, []):
                if evidence.source_url in seen_urls:
                    continue
                seen_urls.add(evidence.source_url)
                merged.append(evidence)
        group.evidences = merged
    return groups


def apply_merge_to_events(
    events: list[Event],
    evidences_by_event: dict[str, list[Evidence]],
    *,
    window_days: int | None = None,
) -> list[MergedEventGroup]:
    """合并 + 挂证据的一站式入口。"""
    groups = merge_events(events, window_days=window_days)
    return attach_evidences(groups, evidences_by_event)
