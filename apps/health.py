"""运行状态与健康检查 — GET /health 返回 git HEAD 与 DB 状态。"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path
from typing import Any

from sqlalchemy import text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import SQLAlchemyError

_ROOT = Path(__file__).resolve().parents[2]


def git_head_sha(repo: Path | None = None) -> str | None:
    root = repo or _ROOT
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=root,
            check=True,
            capture_output=True,
            text=True,
        )
        return result.stdout.strip() or None
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None


def check_database(engine: Engine) -> bool:
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except SQLAlchemyError:
        return False


def health_payload(engine: Engine | None = None) -> dict[str, Any]:
    from packages.domain.database import engine as default_engine

    eng = engine or default_engine
    return {
        "status": "ok" if check_database(eng) else "degraded",
        "version": git_head_sha(),
        "service": os.getenv("SERVICE_NAME", "target-intelligence"),
        "database": "up" if check_database(eng) else "down",
    }


def create_app(engine: Engine | None = None) -> Any:
    """FastAPI 应用工厂；未安装 fastapi 时供测试 mock。"""
    from fastapi import FastAPI

    app = FastAPI(title="Target Intelligence Health", version="0.1.0")

    @app.get("/health")
    def health() -> dict[str, Any]:
        return health_payload(engine)

    return app
