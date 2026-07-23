"""摘要级结构化抽取（规则；LLM 占位后续 001e）。"""

from __future__ import annotations

import re
from typing import Any

from packages.entity_resolution.target_dictionary import TargetDictionary
from packages.source_adapters.pubmed.parser import infer_study_type


def extract_publication_fields(
    record: dict[str, Any],
    *,
    target_dictionary: TargetDictionary | None = None,
) -> dict[str, Any]:
    title = str(record.get("title") or "")
    abstract = record.get("abstract")
    text = f"{title} {abstract or ''}"

    dictionary = target_dictionary or TargetDictionary.from_config_dir()
    matched_targets = []
    for entry in dictionary.all_entries():
        for alias in (entry.canonical_name, *entry.aliases):
            if re.search(re.escape(alias), text, re.IGNORECASE):
                matched_targets.append(entry.canonical_name)
                break

    return {
        "study_type": infer_study_type(title, str(abstract) if abstract else None),
        "matched_targets": sorted(set(matched_targets)),
        "retracted": bool(record.get("retracted")),
        "has_abstract": bool(abstract),
    }
