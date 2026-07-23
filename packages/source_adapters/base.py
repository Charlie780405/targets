"""数据源适配器基类与 DTO。"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Protocol


@dataclass(frozen=True)
class FetchedDocument:
    """单次抓取的结构化文档（适配器输出，processor 输入）。"""

    external_id: str
    source_id: str
    source_name: str
    source_url: str
    title: str | None
    published_at: datetime | None
    content_hash: str
    payload: dict[str, Any]


class SourceAdapter(Protocol):
    source_id: str
    source_name: str

    def fetch(self, since: datetime | None = None) -> list[FetchedDocument]: ...
