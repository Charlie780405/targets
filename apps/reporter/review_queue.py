"""审核队列 — 按 relevance 选取待审文献导出 Vault。"""

from __future__ import annotations

import re
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml  # type: ignore[import-untyped]
from sqlalchemy import select
from sqlalchemy.orm import Session

from apps.processor.publication_relevance import publication_relevance_for_event
from packages.domain.enums import EventType, MedicalReviewStatus
from packages.domain.models import Event, Evidence

_CONFIG_PATH = Path(__file__).resolve().parents[2] / "config" / "relevance_profile.yaml"


@lru_cache(maxsize=1)
def load_relevance_profile() -> dict[str, Any]:
    if not _CONFIG_PATH.is_file():
        return {}
    raw = yaml.safe_load(_CONFIG_PATH.read_text(encoding="utf-8"))
    return raw if isinstance(raw, dict) else {}


def apply_relevance_profile(
    *,
    title: str,
    abstract: str | None,
    base_score: float,
    config: dict[str, Any] | None = None,
) -> float:
    """在基础 relevance 上叠加管线优先/惩罚词。"""
    cfg = config or load_relevance_profile()
    text = f"{title} {abstract or ''}"
    score = base_score
    for item in cfg.get("priority_boosts", []):
        if re.search(str(item["pattern"]), text):
            score += float(item.get("boost", 0))
    for item in cfg.get("penalty_patterns", []):
        if re.search(str(item["pattern"]), text):
            unless = item.get("unless")
            if unless and re.search(str(unless), text):
                continue
            score -= float(item.get("penalty", 0))
    return max(0.0, min(1.0, score))


def profiled_publication_relevance(
    session: Session,
    event: Event,
    evidences: list[Evidence],
) -> float:
    base = publication_relevance_for_event(session, event, evidences)
    if base is None:
        return 0.0
    from packages.domain.models import Publication

    publication: Publication | None = None
    for evidence in evidences:
        if evidence.id.startswith("EVD-PM-"):
            publication = session.get(Publication, evidence.id.removeprefix("EVD-PM-"))
            break
    abstract = publication.abstract if publication else None
    return apply_relevance_profile(title=event.title, abstract=abstract, base_score=base)


def select_review_queue_event_ids(session: Session) -> set[str]:
    """待审 publication 按 profiled relevance 取 Top-N。"""
    cfg = load_relevance_profile()
    top_n = int(cfg.get("review_queue_size", 10))
    export_approved = bool(cfg.get("export_approved_always", True))

    selected: set[str] = set()
    if export_approved:
        approved = session.scalars(
            select(Event.id).where(
                Event.event_type == EventType.PUBLICATION,
                Event.medical_review_status == MedicalReviewStatus.APPROVED,
            )
        ).all()
        selected.update(str(eid) for eid in approved)

    pending_pubs = list(
        session.scalars(
            select(Event).where(
                Event.event_type == EventType.PUBLICATION,
                Event.medical_review_status == MedicalReviewStatus.PENDING,
            )
        ).all()
    )
    scored: list[tuple[float, str]] = []
    for event in pending_pubs:
        evidences = list(session.scalars(select(Evidence).where(Evidence.event_id == event.id)).all())
        rel = profiled_publication_relevance(session, event, evidences)
        scored.append((rel, event.id))
    scored.sort(key=lambda x: (-x[0], x[1]))
    for _rel, eid in scored[:top_n]:
        selected.add(eid)
    return selected
