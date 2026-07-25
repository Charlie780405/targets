"""文献 LLM 分析 — 结构化 JSON，失败规则降级。"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Literal, cast

from pydantic import BaseModel, Field, ValidationError

from apps.processor.llm_extract import _call_openai, _parse_json_payload
from apps.processor.publication_relevance import score_publication_relevance

_PROMPTS_DIR = Path(__file__).resolve().parents[2] / "prompts"


class PublicationAnalysisResult(BaseModel):
    relevance_score: float = Field(ge=0.0, le=1.0)
    summary_zh: str = Field(min_length=1, max_length=800)
    key_findings: str = Field(min_length=1, max_length=600)
    il4ra_linkage: str = Field(min_length=1, max_length=200)
    limitations: str | None = Field(default=None, max_length=300)
    suggested_action: Literal["needs_info"] = "needs_info"


def rule_based_publication_analysis(
    *,
    title: str,
    abstract: str | None,
    matched_targets: list[str],
    study_type: str,
) -> PublicationAnalysisResult:
    rel = score_publication_relevance(
        title=title,
        abstract=abstract,
        matched_targets=matched_targets,
        study_type=study_type,
    )
    snippet = (abstract or title)[:400]
    linkage = "直接" if rel >= 0.7 else ("间接" if rel >= 0.45 else "弱相关")
    return PublicationAnalysisResult(
        relevance_score=round(rel, 2),
        summary_zh=f"{title[:200]}（规则降级摘要）",
        key_findings=snippet,
        il4ra_linkage=f"{linkage} — 待人工确认与 IL-4Rα 管线的关联",
        limitations="规则抽取，未调用 LLM；待人工阅读原文",
        suggested_action="needs_info",
    )


def llm_publication_analysis(
    *,
    title: str,
    abstract: str | None,
    doi: str | None,
    pmid: str | None,
    study_type: str,
    matched_targets: list[str],
) -> PublicationAnalysisResult | None:
    template = (_PROMPTS_DIR / "publication_analysis.md").read_text(encoding="utf-8")
    prompt = (
        template.replace("{{ title }}", title)
        .replace("{{ doi }}", doi or "—")
        .replace("{{ pmid }}", pmid or "—")
        .replace("{{ study_type }}", study_type)
        .replace("{{ matched_targets }}", ", ".join(matched_targets) or "—")
        .replace("{{ abstract }}", abstract or "（无摘要）")
    )
    raw = _call_openai(prompt)
    if raw is None:
        return None
    try:
        payload = _parse_json_payload(raw)
        result = PublicationAnalysisResult.model_validate(payload)
        # 强制 needs_info，禁止 LLM 自批 approved
        return result.model_copy(update={"suggested_action": "needs_info"})
    except (json.JSONDecodeError, ValidationError, TypeError):
        return None


def analyze_publication(
    *,
    title: str,
    abstract: str | None,
    doi: str | None = None,
    pmid: str | None = None,
    study_type: str = "other",
    matched_targets: list[str] | None = None,
    use_llm: bool = True,
) -> tuple[PublicationAnalysisResult, Literal["llm", "rule"]]:
    targets = matched_targets or []
    if use_llm:
        llm_result = llm_publication_analysis(
            title=title,
            abstract=abstract,
            doi=doi,
            pmid=pmid,
            study_type=study_type,
            matched_targets=targets,
        )
        if llm_result is not None:
            return llm_result, "llm"
    return rule_based_publication_analysis(
        title=title,
        abstract=abstract,
        matched_targets=targets,
        study_type=study_type,
    ), "rule"


def analysis_to_payload(result: PublicationAnalysisResult) -> dict[str, Any]:
    return cast(dict[str, Any], result.model_dump())
