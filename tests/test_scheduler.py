"""常驻调度器的安全配置与 WeKnora 同步命令回归。"""

from __future__ import annotations

from pathlib import Path

from apps.collector.scheduler import (
    build_weknora_sync_command,
    load_weknora_sync_config,
)


def test_weknora_sync_is_disabled_by_default() -> None:
    assert load_weknora_sync_config({}) is None


def test_enabled_weknora_sync_requires_complete_non_secret_config(tmp_path: Path) -> None:
    key_file = tmp_path / "weknora.key"
    key_file.write_text("test-only-key\n", encoding="utf-8")
    key_file.chmod(0o600)

    config = load_weknora_sync_config(
        {
            "WEKNORA_SYNC_ENABLED": "true",
            "WEKNORA_BASE_URL": "https://weknora.example",
            "WEKNORA_TARGETS_KB_ID": "kb-1",
            "WEKNORA_TARGETS_API_KEY_FILE": str(key_file),
            "WEKNORA_SYNC_HOUR": "8",
            "WEKNORA_SYNC_MINUTE": "15",
        }
    )

    assert config is not None
    assert config.base_url == "https://weknora.example"
    assert config.knowledge_base_id == "kb-1"
    assert config.api_key_file == key_file
    assert config.hour == 8
    assert config.minute == 15
    command = build_weknora_sync_command(config)
    assert "test-only-key" not in command
    assert str(key_file) in command


def test_incomplete_or_insecure_key_configuration_is_skipped(tmp_path: Path) -> None:
    key_file = tmp_path / "weknora.key"
    key_file.write_text("test-only-key\n", encoding="utf-8")
    key_file.chmod(0o644)

    assert load_weknora_sync_config(
        {
            "WEKNORA_SYNC_ENABLED": "true",
            "WEKNORA_BASE_URL": "https://weknora.example",
            "WEKNORA_TARGETS_KB_ID": "kb-1",
            "WEKNORA_TARGETS_API_KEY_FILE": str(key_file),
        }
    ) is None
    assert load_weknora_sync_config(
        {
            "WEKNORA_SYNC_ENABLED": "true",
            "WEKNORA_BASE_URL": "https://weknora.example",
            "WEKNORA_TARGETS_KB_ID": "kb-1",
            "WEKNORA_TARGETS_API_KEY_FILE": "",
        }
    ) is None


def test_environment_key_source_never_enters_command() -> None:
    config = load_weknora_sync_config(
        {
            "WEKNORA_SYNC_ENABLED": "true",
            "WEKNORA_BASE_URL": "https://weknora.example",
            "WEKNORA_TARGETS_KB_ID": "kb-1",
            "WEKNORA_TARGETS_API_KEY_FILE": "",
            "WEKNORA_TARGETS_API_KEY_ENV": "TEST_WEKNORA_KEY",
            "TEST_WEKNORA_KEY": "test-only-key",
        }
    )

    assert config is not None
    command = build_weknora_sync_command(config)
    assert "test-only-key" not in command
    assert command[-2:] == ["--api-key-env", "TEST_WEKNORA_KEY"]
