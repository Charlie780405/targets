"""内容哈希 — 去重与版本比较 SSOT。"""

import hashlib
import json
from typing import Any


def compute_content_hash(payload: str | bytes | dict[str, Any] | list[Any]) -> str:
    """对规范化内容计算 SHA-256 十六进制摘要。"""
    if isinstance(payload, dict | list):
        normalized = json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
        data = normalized.encode("utf-8")
    elif isinstance(payload, str):
        data = payload.encode("utf-8")
    else:
        data = payload
    return hashlib.sha256(data).hexdigest()
