"""同步 WeKnora 批准文献到 Targets 本地待审投影。

默认只写 Targets SQLite/PostgreSQL 的待审数据，不触发 Vault 发布、LLM 结论或
医学审核。再次执行会按 ``knowledge_base_id + artifact_id`` 幂等更新，并把本次
完整集合中消失的工件保留为 revoked 审计状态。
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path

from apps.collector.weknora_literature import (
    PullError,
    WeKnoraClient,
    read_api_key,
    sync_collection,
)
from packages.domain.database import SessionLocal
from packages.domain.env import load_project_env


def run_sync(
    *,
    base_url: str,
    knowledge_base_id: str,
    api_key: str,
    page_size: int = 100,
    dry_run: bool = False,
) -> dict[str, int]:
    with WeKnoraClient(base_url, api_key) as client:
        collection = client.pull_collection(knowledge_base_id, page_size=page_size)
    if dry_run:
        return {"fetched": collection.total, "created": 0, "updated": 0, "unchanged": 0, "revoked": 0}

    session = SessionLocal()
    try:
        stats = sync_collection(session, knowledge_base_id, collection)
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
    return {
        "fetched": collection.total,
        "created": stats.created,
        "updated": stats.updated,
        "unchanged": stats.unchanged,
        "revoked": stats.revoked,
    }


def main(argv: list[str] | None = None) -> int:
    load_project_env()
    parser = argparse.ArgumentParser(description="同步 WeKnora 批准文献到 Targets 待审投影")
    base_url = os.getenv("WEKNORA_BASE_URL")
    parser.add_argument("--base-url", default=base_url, required=not base_url)
    parser.add_argument("--knowledge-base-id", required=True)
    parser.add_argument("--api-key-env", default="WEKNORA_TARGETS_API_KEY")
    parser.add_argument("--api-key-file", type=Path)
    parser.add_argument("--page-size", type=int, default=100)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)
    if args.api_key_file is not None and args.api_key_env != "WEKNORA_TARGETS_API_KEY":
        parser.error("--api-key-file 与自定义 --api-key-env 只能二选一")
    if args.api_key_file is not None:
        try:
            if args.api_key_file.stat().st_mode & 0o077:
                parser.error("API Key 文件必须是 owner-only（权限不超过 0600）")
        except OSError:
            parser.error("无法读取 API Key 文件")
    try:
        api_key = read_api_key(env_name=args.api_key_env, file_path=args.api_key_file)
        stats = run_sync(
            base_url=args.base_url,
            knowledge_base_id=args.knowledge_base_id,
            api_key=api_key,
            page_size=args.page_size,
            dry_run=args.dry_run,
        )
    except PullError as exc:
        parser.exit(1, f"[失败] {exc}\n")
    print(
        "[通过] WeKnora 文献同步："
        + " ".join(f"{key}={value}" for key, value in stats.items())
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
