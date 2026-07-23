"""三分数规则评分 — 读 config/scoring.yaml SSOT。"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from functools import lru_cache
from pathlib import Path
from typing import Any, cast

import yaml  # type: ignore[import-untyped]

from apps.processor.source_reliability import confidence_from_evidence_level
from packages.domain.enums import EventType, Phase
from packages.domain.models import Event, Evidence

_CONFIG_PATH = Path(__file__).resolve().parents[2] / "config" / "scoring.yaml"


@dataclass(frozen=True)
class ScoreBreakdown:
    significance_score: float
    confidence_score: float
    novelty_score: float
    components: dict[str, float]


@lru_cache(maxsize=1)
def load_scoring_config() -> dict[str, Any]:
    with _CONFIG_PATH.open(encoding="utf-8") as fh:
        return cast(dict[str, Any], yaml.safe_load(fh))


def _clamp(value: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, value))


def significance_label(score: float, config: dict[str, Any] | None = None) -> str:
    cfg = config or load_scoring_config()
    labels = cfg["labels"]
    if score >= labels["significance_high"]:
        return "高"
    if score >= labels["significance_medium"]:
        return "中"
    return "低"


def confidence_label(score: float, config: dict[str, Any] | None = None) -> str:
    cfg = config or load_scoring_config()
    labels = cfg["labels"]
    if score >= labels["confidence_high"]:
        return "高"
    if score >= labels["confidence_medium"]:
        return "中"
    return "低（待核实）"


def _phase_key(phase: Phase | None) -> str:
    if phase is None:
        return "default"
    mapping = {
        Phase.PHASE_3: "phase_3",
        Phase.PHASE_2_3: "phase_2_3",
        Phase.PHASE_2: "phase_2",
        Phase.PHASE_1: "phase_1",
        Phase.PHASE_1_2: "phase_2",
    }
    return mapping.get(phase, "default")


def compute_significance(event: Event, config: dict[str, Any] | None = None) -> float:
    """医学重要性 → significance_score。"""
    import re

    cfg = config or load_scoring_config()
    rules = cfg["significance_rules"]
    event_key = event.event_type.value if isinstance(event.event_type, EventType) else str(event.event_type)
    type_rules = rules.get(event_key, {})
    phase_key = _phase_key(event.phase)
    base = float(type_rules.get(phase_key, type_rules.get("default", 0.50)))

    text = f"{event.title} {event.summary or ''}"
    for item in cfg.get("significance_keyword_boosts", []):
        if re.search(item["pattern"], text):
            base += float(item["boost"])

    return _clamp(base)


def compute_confidence(
    event: Event,
    evidences: list[Evidence],
    config: dict[str, Any] | None = None,
) -> float:
    """来源可靠性 + 交叉验证 → confidence_score。"""
    cfg = config or load_scoring_config()
    conf_cfg = cfg["confidence"]

    if not evidences:
        return 0.40

    levels = [confidence_from_evidence_level(ev.evidence_level) for ev in evidences]
    base = sum(levels) / len(levels)

    if len(evidences) >= 2:
        boost = conf_cfg["multi_source_boost_per_evidence"] * (len(evidences) - 1)
        return _clamp(base + boost, hi=float(conf_cfg["multi_source_cap"]))

    return _clamp(base, hi=float(conf_cfg["single_source_cap"]))


def _similar_event(event: Event, other: Event) -> bool:
    if event.id == other.id:
        return False
    if event.event_type != other.event_type:
        return False
    if event.target_id and other.target_id and event.target_id != other.target_id:
        return False
    return not (event.asset_id and other.asset_id and event.asset_id != other.asset_id)


def compute_novelty(
    event: Event,
    prior_events: list[Event],
    *,
    reference_date: date | None = None,
    config: dict[str, Any] | None = None,
) -> float:
    """与既往事件比对 → novelty_score。"""
    cfg = config or load_scoring_config()
    novelty_cfg = cfg["novelty"]
    ref = reference_date or event.event_date
    window_start = ref - timedelta(days=int(novelty_cfg["lookback_days"]))

    for prior in prior_events:
        if prior.event_date < window_start or prior.event_date > ref:
            continue
        if _similar_event(event, prior):
            return float(novelty_cfg["duplicate_penalty"])

    return float(novelty_cfg["fresh_score"])


def _target_relevance(event: Event) -> float:
    if event.target_id:
        return 1.0
    if event.asset_id:
        return 0.85
    return 0.50


def _time_sensitivity(event: Event, reference_date: date | None = None, config: dict[str, Any] | None = None) -> float:
    cfg = config or load_scoring_config()
    ts = cfg["time_sensitivity"]
    ref = reference_date or datetime.now(tz=UTC).date()
    days_old = (ref - event.event_date).days
    if days_old <= int(ts["full_score_days"]):
        return 1.0
    decay = int(ts["decay_days"])
    if days_old >= decay:
        return float(ts["min_score"])
    ratio = 1.0 - (days_old - int(ts["full_score_days"])) / decay
    return _clamp(float(ts["min_score"]) + ratio * (1.0 - float(ts["min_score"])))


def compute_weighted_total(components: dict[str, float], config: dict[str, Any] | None = None) -> float:
    """加权总分（仅用于排序/调试，不写入 Event 单列）。"""
    cfg = config or load_scoring_config()
    weights = cfg["weights"]
    total = sum(components.get(k, 0.0) * float(weights[k]) for k in weights)
    return _clamp(total)


def score_event(
    event: Event,
    evidences: list[Evidence],
    prior_events: list[Event] | None = None,
    *,
    reference_date: date | None = None,
    config: dict[str, Any] | None = None,
) -> ScoreBreakdown:
    """计算三分数及组件（组件供审计，不替代分列存储）。"""
    cfg = config or load_scoring_config()
    prior = prior_events or []

    source_rel = compute_confidence(event, evidences, cfg)
    medical_imp = compute_significance(event, cfg)
    novelty = compute_novelty(event, prior, reference_date=reference_date, config=cfg)
    target_rel = _target_relevance(event)
    time_sens = _time_sensitivity(event, reference_date, cfg)

    components = {
        "source_reliability": source_rel,
        "medical_importance": medical_imp,
        "novelty": novelty,
        "target_relevance": target_rel,
        "time_sensitivity": time_sens,
    }

    return ScoreBreakdown(
        significance_score=medical_imp,
        confidence_score=source_rel,
        novelty_score=novelty,
        components=components,
    )
