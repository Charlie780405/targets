"""公司披露标题/摘要 → 事件类型分类（规则；001e 可升级 LLM）。"""

from __future__ import annotations

import re

from packages.domain.enums import EventType

DEAL_KEYWORDS = (
    r"\bacquisition\b",
    r"\blicense\b",
    r"\blicensing\b",
    r"\bcollaboration\b",
    r"\bpartnership\b",
    r"\bfinancing\b",
    r"\binvestment\b",
    r"\bmerger\b",
    r"\bagreement\b",
    r"\b授权\b",
    r"\b合作\b",
    r"\b融资\b",
)

CLINICAL_KEYWORDS = (
    r"\bphase [1234]\b",
    r"\bphase iii\b",
    r"\bphase ii\b",
    r"\bprimary endpoint\b",
    r"\btopline\b",
    r"\btop-line\b",
    r"\bmet its primary\b",
    r"\bclinical trial results\b",
    r"\b主要终点\b",
    r"\b临床结果\b",
)


def classify_company_release(title: str, summary: str | None = None) -> EventType | None:
    text = f"{title} {summary or ''}".lower()
    if any(re.search(p, text) for p in CLINICAL_KEYWORDS):
        return EventType.CLINICAL_RESULT
    if any(re.search(p, text) for p in DEAL_KEYWORDS):
        return EventType.DEAL
    return None
