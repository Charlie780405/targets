"""文献相关性规则评分 — 读 config/publication_filter.yaml。"""

from __future__ import annotations

import re
from functools import lru_cache
from pathlib import Path
from typing import Any, cast

import yaml  # type: ignore[import-untyped]

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
