"""The resident scheduler no longer registers or configures WeKnora ingestion."""

from __future__ import annotations

import apps.collector.scheduler as scheduler_module


class _SchedulerStub:
    def __init__(self, *, timezone: str) -> None:
        self.timezone = timezone
        self.jobs: list[dict[str, object]] = []
        self.started = False

    def add_job(self, _callable, _trigger: str, **kwargs: object) -> None:  # type: ignore[no-untyped-def]
        self.jobs.append(kwargs)

    def start(self) -> None:
        self.started = True


def test_scheduler_has_no_weknora_registration_or_configuration(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    scheduler = _SchedulerStub(timezone="UTC")
    monkeypatch.setattr(scheduler_module, "BlockingScheduler", lambda **_kwargs: scheduler)
    monkeypatch.setattr(scheduler_module, "load_project_env", lambda: None)

    scheduler_module.main()

    assert scheduler.started is True
    assert {job["id"] for job in scheduler.jobs} == {
        "collect_ctgov",
        "collect_pubmed",
        "collect_companies",
        "weekly",
    }
    assert not hasattr(scheduler_module, "load_weknora_sync_config")
    assert not hasattr(scheduler_module, "build_weknora_sync_command")
    assert not hasattr(scheduler_module, "run_weknora_sync")
