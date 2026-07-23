"""来源可靠性 → confidence 输入（SSOT 映射）。"""

from __future__ import annotations

from packages.domain.enums import EvidenceLevel

# evidence_level → 初始 confidence 分（001e 规则评分会再调整）
EVIDENCE_LEVEL_CONFIDENCE: dict[str, float] = {
    EvidenceLevel.A: 0.95,
    EvidenceLevel.B: 0.85,
    EvidenceLevel.C: 0.70,
    EvidenceLevel.D: 0.60,
    EvidenceLevel.E: 0.40,
}


def confidence_from_evidence_level(level: str | EvidenceLevel) -> float:
    key = str(level).upper()
    return EVIDENCE_LEVEL_CONFIDENCE.get(key, 0.50)
