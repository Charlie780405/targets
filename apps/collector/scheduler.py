"""APScheduler 常驻采集调度（docker-compose scheduler profile 可选）。"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from apscheduler.schedulers.blocking import BlockingScheduler  # type: ignore[import-untyped]

_ROOT = Path(__file__).resolve().parents[2]


def _run(module: str) -> None:
    subprocess.run([sys.executable, "-m", module], cwd=_ROOT, check=False)


def run_weekly_publish() -> None:
    vault = os.getenv("VAULT_PATH", str(_ROOT / "vault"))
    subprocess.run(
        [sys.executable, "-m", "apps.reporter.publish", "--vault", vault, "--no-weekly"],
        cwd=_ROOT,
        check=False,
    )


def main() -> None:
    scheduler = BlockingScheduler(timezone="UTC")
    scheduler.add_job(
        lambda: _run("apps.collector.run_clinicaltrials"),
        "cron",
        hour=6,
        minute=0,
        id="collect_ctgov",
    )
    scheduler.add_job(
        lambda: _run("apps.collector.run_pubmed"),
        "cron",
        hour=6,
        minute=15,
        id="collect_pubmed",
    )
    scheduler.add_job(
        lambda: _run("apps.collector.run_companies"),
        "cron",
        hour=6,
        minute=30,
        id="collect_companies",
    )
    scheduler.add_job(run_weekly_publish, "cron", day_of_week="mon", hour=7, minute=0, id="weekly")
    scheduler.start()


if __name__ == "__main__":
    main()
