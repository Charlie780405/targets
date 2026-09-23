"""APScheduler 常驻采集调度（docker-compose scheduler profile 可选）。"""

from __future__ import annotations

import logging
import os
import subprocess
import sys
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlsplit

from apscheduler.schedulers.blocking import BlockingScheduler  # type: ignore[import-untyped]

from packages.domain.env import load_project_env

_ROOT = Path(__file__).resolve().parents[2]
LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True)
class WeKnoraSyncConfig:
    """定时同步所需的非秘密配置；密钥只在子进程中由文件或环境读取。"""

    base_url: str
    knowledge_base_id: str
    api_key_file: Path | None
    api_key_env: str
    hour: int
    minute: int


def _is_enabled(value: str) -> bool:
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _parse_clock(value: str, *, maximum: int) -> int | None:
    try:
        parsed = int(value)
    except ValueError:
        return None
    return parsed if 0 <= parsed <= maximum else None


def load_weknora_sync_config(
    values: Mapping[str, str] | None = None,
) -> WeKnoraSyncConfig | None:
    """读取安全的 WeKnora 调度配置；未完整配置时不注册作业。"""

    source = os.environ if values is None else values
    if not _is_enabled(source.get("WEKNORA_SYNC_ENABLED", "false")):
        return None

    base_url = source.get("WEKNORA_BASE_URL", "").strip().rstrip("/")
    parsed_url = urlsplit(base_url)
    knowledge_base_id = source.get("WEKNORA_TARGETS_KB_ID", "").strip()
    if (
        parsed_url.scheme not in {"http", "https"}
        or not parsed_url.hostname
        or parsed_url.username
        or parsed_url.password
        or parsed_url.query
        or parsed_url.fragment
        or not knowledge_base_id
    ):
        LOGGER.warning("WeKnora 定时同步已开启，但 base URL 或 KB ID 配置不完整，跳过注册")
        return None

    raw_key_file = source.get("WEKNORA_TARGETS_API_KEY_FILE")
    if raw_key_file is None:
        raw_key_file = str(_ROOT / "secrets" / "weknora-targets-retrieve.key")
    raw_key_file = raw_key_file.strip()
    api_key_file: Path | None = None
    if raw_key_file:
        api_key_file = Path(raw_key_file).expanduser()
        if not api_key_file.is_absolute():
            api_key_file = _ROOT / api_key_file
        try:
            mode = api_key_file.stat().st_mode
        except OSError:
            LOGGER.warning("WeKnora 定时同步密钥文件不存在或不可读取，跳过注册")
            return None
        if not api_key_file.is_file() or mode & 0o077:
            LOGGER.warning("WeKnora 定时同步密钥文件必须是 owner-only，跳过注册")
            return None
    else:
        api_key_env = source.get("WEKNORA_TARGETS_API_KEY_ENV", "WEKNORA_TARGETS_API_KEY").strip()
        api_key = source.get(api_key_env, "").strip()
        if not api_key or any(char.isspace() for char in api_key):
            LOGGER.warning("WeKnora 定时同步 API Key 环境变量未配置，跳过注册")
            return None
        if not api_key_env or not api_key_env.replace("_", "").isalnum() or api_key_env[0].isdigit():
            LOGGER.warning("WeKnora 定时同步 API Key 环境变量名无效，跳过注册")
            return None

    hour = _parse_clock(source.get("WEKNORA_SYNC_HOUR", "7"), maximum=23)
    minute = _parse_clock(source.get("WEKNORA_SYNC_MINUTE", "0"), maximum=59)
    if hour is None or minute is None:
        LOGGER.warning("WeKnora 定时同步时间配置无效，跳过注册")
        return None

    return WeKnoraSyncConfig(
        base_url=base_url,
        knowledge_base_id=knowledge_base_id,
        api_key_file=api_key_file,
        api_key_env=source.get("WEKNORA_TARGETS_API_KEY_ENV", "WEKNORA_TARGETS_API_KEY").strip()
        or "WEKNORA_TARGETS_API_KEY",
        hour=hour,
        minute=minute,
    )


def build_weknora_sync_command(config: WeKnoraSyncConfig) -> list[str]:
    command = [
        sys.executable,
        "-m",
        "apps.collector.run_weknora_literature",
        "--base-url",
        config.base_url,
        "--knowledge-base-id",
        config.knowledge_base_id,
    ]
    if config.api_key_file is not None:
        command.extend(["--api-key-file", str(config.api_key_file)])
    else:
        command.extend(["--api-key-env", config.api_key_env])
    return command


def _run(module: str) -> None:
    subprocess.run([sys.executable, "-m", module], cwd=_ROOT, check=False)


def run_weekly_publish() -> None:
    vault = os.getenv("VAULT_PATH", str(_ROOT / "vault"))
    subprocess.run(
        [sys.executable, "-m", "apps.reporter.publish", "--vault", vault, "--no-weekly"],
        cwd=_ROOT,
        check=False,
    )


def run_weknora_sync(config: WeKnoraSyncConfig) -> None:
    """执行一次只读拉取/本地投影同步，不把密钥放入命令参数。"""

    result = subprocess.run(build_weknora_sync_command(config), cwd=_ROOT, check=False)
    if result.returncode:
        LOGGER.warning("WeKnora 文献同步失败，退出码=%s；下次调度将重试", result.returncode)
    else:
        LOGGER.info("WeKnora 文献同步完成")


def main() -> None:
    load_project_env()
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
    weknora_config = load_weknora_sync_config()
    if weknora_config is not None:
        scheduler.add_job(
            lambda: run_weknora_sync(weknora_config),
            "cron",
            hour=weknora_config.hour,
            minute=weknora_config.minute,
            id="sync_weknora_literature",
            max_instances=1,
            coalesce=True,
            misfire_grace_time=3600,
        )
        LOGGER.info(
            "已注册 WeKnora 文献同步：UTC %02d:%02d，KB=%s",
            weknora_config.hour,
            weknora_config.minute,
            weknora_config.knowledge_base_id,
        )
    scheduler.start()


if __name__ == "__main__":
    main()
