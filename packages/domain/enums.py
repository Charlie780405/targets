"""领域枚举 SSOT — 禁止在业务代码中硬编码这些字面量。"""

from enum import StrEnum


class EventType(StrEnum):
    TRIAL_CHANGE = "trial_change"
    CLINICAL_RESULT = "clinical_result"
    REGULATORY = "regulatory"
    PUBLICATION = "publication"
    DEAL = "deal"
    CONGRESS = "congress"


class ResultDirection(StrEnum):
    POSITIVE = "positive"
    NEGATIVE = "negative"
    MIXED = "mixed"
    INCONCLUSIVE = "inconclusive"
    NA = "na"


class Phase(StrEnum):
    PRECLINICAL = "preclinical"
    PHASE_1 = "phase_1"
    PHASE_1_2 = "phase_1_2"
    PHASE_2 = "phase_2"
    PHASE_2_3 = "phase_2_3"
    PHASE_3 = "phase_3"
    PHASE_4 = "phase_4"
    NA = "na"


class MedicalReviewStatus(StrEnum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    NEEDS_INFO = "needs_info"


class EvidenceLevel(StrEnum):
    A = "A"
    B = "B"
    C = "C"
    D = "D"
    E = "E"


class ReportType(StrEnum):
    DAILY = "daily"
    WEEKLY = "weekly"
