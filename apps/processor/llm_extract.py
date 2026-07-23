"""LLM 结构化抽取 — Pydantic 校验，失败降级规则抽取。"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any, Literal, cast

from pydantic import BaseModel, Field, ValidationError

from packages.domain.models import Event, Evidence

_PROMPTS_DIR = Path(__file__).resolve().parents[2] / "prompts"


class EventExtractResult(BaseModel):
    summary_zh: str = Field(min_length=1, max_length=500)
    impact: str = Field(min_length=1, max_length=300)
    uncertainty: str | None = Field(default=None, max_length=300)


class WeeklySummaryResult(BaseModel):
    executive_summary: str = Field(min_length=1, max_length=300)
    watch_items: list[str] = Field(default_factory=list, max_length=8)


ExtractMethod = Literal["llm", "rule"]


def _load_prompt(name: str) -> str:
    return (_PROMPTS_DIR / name).read_text(encoding="utf-8")


def _evidence_snippets(evidences: list[Evidence]) -> str:
    if not evidences:
        return "（无证据片段）"
    lines = []
    for i, ev in enumerate(evidences, 1):
        snippet = ev.evidence_snippet or "—"
        lines.append(f"{i}. [{ev.source_name}] {snippet}")
    return "\n".join(lines)


def rule_based_extract(event: Event, evidences: list[Evidence]) -> EventExtractResult:
    """无 LLM 时的规则降级抽取。"""
    snippets = [ev.evidence_snippet for ev in evidences if ev.evidence_snippet]
    summary_zh = event.summary or (snippets[0] if snippets else event.title)
    if len(evidences) == 1:
        uncertainty = "单一来源，待交叉验证"
    elif not snippets:
        uncertainty = "证据片段缺失，待补采"
    else:
        uncertainty = None
    impact = f"需结合 {event.event_type.value} 类型与 IL-4Rα 管线位置人工研判。"
    return EventExtractResult(
        summary_zh=summary_zh[:500],
        impact=impact[:300],
        uncertainty=uncertainty,
    )


def _parse_json_payload(raw: str) -> dict[str, object]:
    text = raw.strip()
    fence = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if fence:
        text = fence.group(1)
    return cast(dict[str, object], json.loads(text))


def validate_event_extract(payload: dict[str, object]) -> EventExtractResult:
    """Schema 校验 — 不合规则抛 ValidationError。"""
    return EventExtractResult.model_validate(payload)


def _call_openai(prompt: str) -> str | None:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        return None
    try:
        from openai import OpenAI  # type: ignore[import-not-found]
    except ImportError:
        return None

    client = OpenAI(api_key=api_key)
    response = client.chat.completions.create(
        model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
        messages=[{"role": "user", "content": prompt}],
        temperature=0.2,
    )
    content: Any = response.choices[0].message.content
    return str(content) if content is not None else None


def llm_extract_event(event: Event, evidences: list[Evidence]) -> EventExtractResult | None:
    """调用 LLM 抽取；失败返回 None 供上层降级。"""
    template = _load_prompt("event_extract.md")
    et = event.event_type.value if hasattr(event.event_type, "value") else str(event.event_type)
    prompt = (
        template.replace("{{ event_type }}", et)
        .replace("{{ title }}", event.title)
        .replace("{{ summary }}", event.summary or "—")
        .replace("{{ evidence_snippets }}", _evidence_snippets(evidences))
    )
    raw = _call_openai(prompt)
    if raw is None:
        return None
    try:
        payload = _parse_json_payload(raw)
        return validate_event_extract(payload)
    except (json.JSONDecodeError, ValidationError, TypeError):
        return None


def extract_event_summary(
    event: Event,
    evidences: list[Evidence],
    *,
    use_llm: bool = True,
) -> tuple[EventExtractResult, ExtractMethod]:
    """LLM 优先，Schema 不合规或不可用则规则降级。"""
    if use_llm:
        llm_result = llm_extract_event(event, evidences)
        if llm_result is not None:
            return llm_result, "llm"
    return rule_based_extract(event, evidences), "rule"


def rule_based_weekly_summary(
    events: list[Event],
    period_start: str,
    period_end: str,
) -> WeeklySummaryResult:
    if not events:
        return WeeklySummaryResult(
            executive_summary=f"{period_start}—{period_end} 本周无新入库事件。",
            watch_items=["持续监测 IL-4Rα 管线 III 期读出与监管动态"],
        )
    titles = [e.title for e in events[:5]]
    summary = f"本周共 {len(events)} 条事件：" + "；".join(titles[:3])
    return WeeklySummaryResult(
        executive_summary=summary[:300],
        watch_items=["跟进待审核事件", "监测试验状态变更"],
    )


def llm_weekly_summary(
    events: list[Event],
    period_start: str,
    period_end: str,
) -> WeeklySummaryResult | None:
    template = _load_prompt("weekly_summary.md")
    events_json = json.dumps(
        [{"title": e.title, "type": e.event_type.value, "date": e.event_date.isoformat()} for e in events],
        ensure_ascii=False,
    )
    prompt = (
        template.replace("{{ period_start }}", period_start)
        .replace("{{ period_end }}", period_end)
        .replace("{{ events_json }}", events_json)
    )
    raw = _call_openai(prompt)
    if raw is None:
        return None
    try:
        payload = _parse_json_payload(raw)
        return WeeklySummaryResult.model_validate(payload)
    except (json.JSONDecodeError, ValidationError, TypeError):
        return None


def extract_weekly_summary(
    events: list[Event],
    period_start: str,
    period_end: str,
    *,
    use_llm: bool = True,
) -> tuple[WeeklySummaryResult, ExtractMethod]:
    if use_llm:
        llm_result = llm_weekly_summary(events, period_start, period_end)
        if llm_result is not None:
            return llm_result, "llm"
    return rule_based_weekly_summary(events, period_start, period_end), "rule"
