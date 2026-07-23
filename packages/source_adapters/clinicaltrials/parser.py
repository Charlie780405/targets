"""ClinicalTrials.gov API v2 响应解析。"""

from __future__ import annotations

import json
from datetime import date
from typing import Any

from packages.domain.content_hash import compute_content_hash
from packages.domain.enums import Phase

# config/sources/clinicaltrials.yaml watch_fields → JSON 路径提取
WATCH_FIELD_KEYS = (
    "OverallStatus",
    "EnrollmentCount",
    "PrimaryCompletionDate",
    "StudyCompletionDate",
    "OutcomeMeasures",
    "ResultsPosted",
    "Sponsor",
    "Locations",
)


def get_nct_id(study: dict[str, Any]) -> str | None:
    ident = study.get("protocolSection", {}).get("identificationModule", {})
    nct_id = ident.get("nctId")
    return str(nct_id) if nct_id else None


def get_brief_title(study: dict[str, Any]) -> str:
    ident = study.get("protocolSection", {}).get("identificationModule", {})
    return str(ident.get("briefTitle") or ident.get("officialTitle") or "Untitled trial")


def build_study_url(nct_id: str) -> str:
    return f"https://clinicaltrials.gov/study/{nct_id}"


def _map_phase(raw_phases: list[str] | None) -> Phase | None:
    if not raw_phases:
        return None
    token = raw_phases[0].upper().replace(" ", "_").replace("-", "_")
    mapping = {
        "PHASE1": Phase.PHASE_1,
        "PHASE2": Phase.PHASE_2,
        "PHASE3": Phase.PHASE_3,
        "PHASE4": Phase.PHASE_4,
        "PHASE1_PHASE2": Phase.PHASE_1_2,
        "PHASE2_PHASE3": Phase.PHASE_2_3,
        "EARLY_PHASE1": Phase.PHASE_1,
    }
    return mapping.get(token)


def _parse_date(value: str | None) -> date | None:
    if not value:
        return None
    # API 可能返回 YYYY-MM 或 YYYY-MM-DD
    parts = value.split("-")
    if len(parts) >= 2:
        year, month = int(parts[0]), int(parts[1])
        day = int(parts[2]) if len(parts) >= 3 else 1
        return date(year, month, day)
    return None


def extract_watch_fields(study: dict[str, Any]) -> dict[str, Any]:
    protocol = study.get("protocolSection", {})
    status = protocol.get("statusModule", {})
    design = protocol.get("designModule", {})
    outcomes = protocol.get("outcomesModule", {})
    sponsor_mod = protocol.get("sponsorCollaboratorsModule", {})
    locations_mod = protocol.get("contactsLocationsModule", {})

    enrollment = design.get("enrollmentInfo") or {}
    primary_outcomes = outcomes.get("primaryOutcomes") or []
    secondary_outcomes = outcomes.get("secondaryOutcomes") or []
    outcome_measures = [
        o.get("measure") for o in primary_outcomes + secondary_outcomes if o.get("measure")
    ]

    lead = sponsor_mod.get("leadSponsor") or {}
    locations = locations_mod.get("locations") or []
    location_summary = [
        f"{loc.get('city', '')}|{loc.get('state', '')}|{loc.get('country', '')}".strip("|")
        for loc in locations
    ]

    return {
        "OverallStatus": status.get("overallStatus"),
        "EnrollmentCount": enrollment.get("count"),
        "PrimaryCompletionDate": (status.get("primaryCompletionDateStruct") or {}).get("date"),
        "StudyCompletionDate": (status.get("completionDateStruct") or {}).get("date"),
        "OutcomeMeasures": outcome_measures,
        "ResultsPosted": study.get("hasResults"),
        "Sponsor": lead.get("name"),
        "Locations": sorted(location_summary),
    }


def parse_trial_record(study: dict[str, Any]) -> dict[str, Any]:
    """JSON → Trial 表字段 + watch_fields。"""
    nct_id = get_nct_id(study)
    if not nct_id:
        raise ValueError("study missing nctId")

    protocol = study.get("protocolSection", {})
    status = protocol.get("statusModule", {})
    design = protocol.get("designModule", {})
    enrollment = design.get("enrollmentInfo") or {}
    watch_fields = extract_watch_fields(study)

    return {
        "id": nct_id,
        "nct_id": nct_id,
        "title": get_brief_title(study),
        "overall_status": status.get("overallStatus"),
        "phase": _map_phase(design.get("phases")),
        "enrollment": enrollment.get("count"),
        "primary_completion_date": _parse_date(
            (status.get("primaryCompletionDateStruct") or {}).get("date")
        ),
        "study_completion_date": _parse_date((status.get("completionDateStruct") or {}).get("date")),
        "outcome_measures": json.dumps(watch_fields.get("OutcomeMeasures") or [], ensure_ascii=False),
        "results_posted": bool(study.get("hasResults")),
        "content_hash": compute_content_hash(watch_fields),
        "watch_fields": watch_fields,
        "watch_fields_hash": compute_content_hash(watch_fields),
    }
