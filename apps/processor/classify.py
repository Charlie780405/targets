"""事件类型分类与归一 — 规则优先，001e 供 scoring/merge 前置。"""

from __future__ import annotations

import re

from apps.processor.company_event_classifier import classify_company_release
from packages.domain.enums import EventType, Phase

# 试验 diff / CT.gov 字段变化关键词
_TRIAL_CHANGE_PATTERNS = (
    r"(?i)\bstatus\b.*\b(completed|terminated|withdrawn|suspended)\b",
    r"(?i)\bprimary completion\b",
    r"(?i)\benrollment\b.*\b(changed|updated|revised)\b",
    r"(?i)\bsponsor\b.*\b(changed|transfer)\b",
    r"(?i)结果已发布|results posted",
)

_CLINICAL_RESULT_PATTERNS = (
    r"(?i)\bphase\s*(iii|3)\b.*\b(endpoint|result|data)\b",
    r"(?i)\bprimary endpoint\b.*\b(met|missed|achieved|failed)\b",
    r"(?i)\btopline\b",
    r"(?i)\b主要终点\b",
    r"(?i)\b临床结果\b",
)

_REGULATORY_PATTERNS = (
    r"(?i)\b(fda|ema|nmpa|pmda)\b.*\b(approv|reject|breakthrough|orphan)\b",
    r"(?i)\b(批准|拒绝|突破性疗法|附条件批准)\b",
)

_PUBLICATION_PATTERNS = (
    r"(?i)\b(published|publication|pubmed|doi|pmid)\b",
    r"(?i)\b(勘误|撤稿|retraction|corrigendum)\b",
)


def classify_from_text(
    title: str,
    summary: str | None = None,
    *,
    current_type: EventType | None = None,
) -> EventType:
    """从标题/摘要推断事件类型；已有类型且为 clinical_result/regulatory 时不降级。"""
    text = f"{title} {summary or ''}"
    if current_type in (EventType.CLINICAL_RESULT, EventType.REGULATORY):
        return current_type

    company_type = classify_company_release(title, summary)
    if company_type is not None:
        return company_type

    if any(re.search(p, text) for p in _CLINICAL_RESULT_PATTERNS):
        return EventType.CLINICAL_RESULT
    if any(re.search(p, text) for p in _REGULATORY_PATTERNS):
        return EventType.REGULATORY
    if any(re.search(p, text) for p in _PUBLICATION_PATTERNS):
        return EventType.PUBLICATION
    if any(re.search(p, text) for p in _TRIAL_CHANGE_PATTERNS):
        return EventType.TRIAL_CHANGE

    return current_type or EventType.TRIAL_CHANGE


def infer_phase_from_text(title: str, summary: str | None = None) -> Phase | None:
    """从文本推断试验阶段（供 scoring significance 使用）。"""
    text = f"{title} {summary or ''}".lower()
    if re.search(r"(?i)\bphase\s*(iii|3)\b|iii\s*期", text):
        return Phase.PHASE_3
    if re.search(r"(?i)\bphase\s*(ii/iii|2/3)\b", text):
        return Phase.PHASE_2_3
    if re.search(r"(?i)\bphase\s*(ii|2)\b|ii\s*期", text):
        return Phase.PHASE_2
    if re.search(r"(?i)\bphase\s*(i|1)\b|i\s*期", text):
        return Phase.PHASE_1
    return None


def enrich_event_classification(
    event_type: EventType,
    title: str,
    summary: str | None,
    phase: Phase | None,
) -> tuple[EventType, Phase | None]:
    """归一事件类型与阶段，供落库前或周报前调用。"""
    resolved_type = classify_from_text(title, summary, current_type=event_type)
    resolved_phase = phase or infer_phase_from_text(title, summary)
    return resolved_type, resolved_phase
