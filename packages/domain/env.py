"""从仓库根目录加载 .env（采集/发布入口共用）。"""

from __future__ import annotations

from pathlib import Path


def load_project_env() -> None:
    try:
        from dotenv import load_dotenv
    except ImportError:
        return
    root = Path(__file__).resolve().parents[2]
    load_dotenv(root / ".env")
