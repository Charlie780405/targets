"""ClinicalTrials.gov 数据源适配器。"""

from packages.source_adapters.clinicaltrials.adapter import (
    ClinicalTrialsAdapter,
    build_query_term,
    load_source_config,
)
from packages.source_adapters.clinicaltrials.parser import (
    WATCH_FIELD_KEYS,
    extract_watch_fields,
    parse_trial_record,
)

__all__ = [
    "WATCH_FIELD_KEYS",
    "ClinicalTrialsAdapter",
    "build_query_term",
    "extract_watch_fields",
    "load_source_config",
    "parse_trial_record",
]
