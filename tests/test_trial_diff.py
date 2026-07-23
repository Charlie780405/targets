"""试验快照 diff 测试。"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from apps.processor.trial_diff import (
    build_trial_change_event,
    diff_watch_fields,
    is_medically_meaningful_change,
)
from packages.domain.models import Trial, TrialSnapshot
from packages.source_adapters.clinicaltrials.parser import extract_watch_fields

_FIXTURES = Path(__file__).resolve().parent / "fixtures" / "clinicaltrials"


def _watch(path: str) -> dict:
    study = json.loads((_FIXTURES / path).read_text(encoding="utf-8"))
    return extract_watch_fields(study)


def test_diff_status_change_is_meaningful() -> None:
    old = _watch("study_v1_recruiting.json")
    new = _watch("study_v2_completed_small_enrollment.json")
    changes = diff_watch_fields(old, new)
    assert any(c.field == "OverallStatus" for c in changes)
    assert is_medically_meaningful_change(changes)


def test_small_enrollment_only_change_is_noise() -> None:
    old = dict(_watch("study_v1_recruiting.json"))
    new = dict(old)
    new["EnrollmentCount"] = 103  # +3
    changes = diff_watch_fields(old, new)
    assert len(changes) == 1
    assert changes[0].field == "EnrollmentCount"
    assert not is_medically_meaningful_change(changes)


def test_results_posted_change_is_meaningful() -> None:
    old = _watch("study_v2_completed_small_enrollment.json")
    new = _watch("study_v3_results_posted.json")
    changes = diff_watch_fields(old, new)
    assert any(c.field == "ResultsPosted" for c in changes)
    assert is_medically_meaningful_change(changes)


def test_build_trial_change_event() -> None:
    trial = Trial(
        id="NCT00000001",
        nct_id="NCT00000001",
        title="Test",
        content_hash="abc",
    )
    old = _watch("study_v1_recruiting.json")
    new = _watch("study_v2_completed_small_enrollment.json")
    changes = diff_watch_fields(old, new)
    event = build_trial_change_event(trial, changes, event_id="EVT-2026-00001")
    assert event.event_type.value == "trial_change"
    assert "OverallStatus" in (event.summary or "")


def test_diff_snapshots_with_previous() -> None:
    from apps.processor.trial_diff import diff_snapshots

    old = _watch("study_v1_recruiting.json")
    new = _watch("study_v2_completed_small_enrollment.json")
    previous = TrialSnapshot(
        trial_id="NCT00000001",
        content_hash="x",
        payload_json=old,
        watch_fields_hash="y",
        snapshot_at=datetime.now(tz=UTC),
    )
    changes = diff_snapshots(previous, new)
    assert len(changes) >= 1
