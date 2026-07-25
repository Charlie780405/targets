"""文献相关性规则评分 — 读 config/publication_filter.yaml。"""

from __future__ import annotations

import re
from functools import lru_cache
from pathlib import Path
from typing import Any, cast

import yaml  # type: ignore[import-untyped]
from sqlalchemy import select
from sqlalchemy.orm import Session

from packages.domain.enums import EventType
from packages.domain.models import Event, Evidence, Publication
from packages.entity_resolution.target_dictionary import TargetDictionary

_CONFIG_PATH = Path(__file__).resolve().parents[2] / "config" / "publication_filter.yaml"


@lru_cache(maxsize=1)
def load_publication_filter_config() -> dict[str, Any]:
    with _CONFIG_PATH.open(encoding="utf-8") as fh:
        return cast(dict[str, Any], yaml.safe_load(fh))


def score_publication_relevance(
    *,
    title: str,
    abstract: str | None,
    matched_targets: list[str],
    study_type: str,
    target_dictionary: TargetDictionary | None = None,
) -> float:
    """0–1 规则分：标题命中靶点、匹配靶点数、研究类型加权。"""
    dictionary = target_dictionary or TargetDictionary.from_config_dir()
    text = f"{title} {abstract or ''}"
    score = 0.0

    if matched_targets:
        score += 0.35
    else:
        for entry in dictionary.all_entries():
            for alias in (entry.canonical_name, *entry.aliases):
                if re.search(re.escape(alias), title, re.IGNORECASE):
                    score += 0.25
                    break

    if abstract and matched_targets:
        for name in matched_targets:
            if re.search(re.escape(name), abstract, re.IGNORECASE):
                score += 0.15
                break

    if study_type == "clinical_trial":
        score += 0.20
    elif study_type == "systematic_review":
        score += 0.15
    elif study_type == "review":
        score += 0.05

    if re.search(r"(?i)\bdupilumab\b|\btralokinumab\b|\bIL-4R", text):
        score += 0.10

    return min(1.0, score)


def min_relevance_for_event(config: dict[str, Any] | None = None) -> float:
    cfg = config or load_publication_filter_config()
    return float(cfg.get("min_relevance_for_event", 0.45))


def export_min_relevance(config: dict[str, Any] | None = None) -> float:
    cfg = config or load_publication_filter_config()
    return float(cfg.get("export_min_relevance", cfg.get("min_relevance_for_event", 0.45)))


def should_prune_vault(config: dict[str, Any] | None = None) -> bool:
    cfg = config or load_publication_filter_config()
    return bool(cfg.get("prune_vault_excluded", True))


def _fields_from_event_summary(summary: str | None) -> tuple[str, list[str]]:
    study_type = "other"
    targets: list[str] = []
    if not summary:
        return study_type, targets
    match = re.search(r"study_type=([^;]+)", summary)
    if match:
        study_type = match.group(1).strip()
    match = re.search(r"targets=([^;]+)", summary)
    if match:
        targets = [t.strip() for t in match.group(1).split(",") if t.strip()]
    return study_type, targets


def publication_relevance_for_event(
    session: Session,
    event: Event,
    evidences: list[Evidence],
) -> float | None:
    """Publication 事件 relevance；非 publication 返回 None（不参与 relevance 门）。"""
    if event.event_type != EventType.PUBLICATION:
        return None
    publication: Publication | None = None
    for evidence in evidences:
        if evidence.id.startswith("EVD-PM-"):
            publication = session.get(Publication, evidence.id.removeprefix("EVD-PM-"))
            if publication:
                break
    if publication is None:
        publication = session.scalar(
            select(Publication).where(Publication.title == event.title).limit(1)
        )
    if publication is None:
        return 0.0
    study_type, targets = _fields_from_event_summary(event.summary)
    return score_publication_relevance(
        title=publication.title,
        abstract=publication.abstract,
        matched_targets=targets,
        study_type=study_type,
    )


def passes_vault_export_gate(
    session: Session,
    event: Event,
    evidences: list[Evidence],
    *,
    min_importance: str | None,
    min_relevance: float,
) -> bool:
    """002b 导出门：rejected / 低 relevance / 低 significance 均不进 Vault。"""
    from packages.domain.enums import MedicalReviewStatus

    if event.medical_review_status == MedicalReviewStatus.REJECTED:
        return False
    relevance = publication_relevance_for_event(session, event, evidences)
    if relevance is not None and relevance < min_relevance:
        return False
    if not min_importance:
        return True
    from apps.processor.scoring import significance_label

    order = {"low": 0, "medium": 1, "high": 2}
    score = event.significance_score or 0.0
    label = significance_label(score)
    band = {"高": "high", "中": "medium", "低": "low"}.get(label, "low")
    return order.get(band, 0) >= order.get(min_importance, 0)
