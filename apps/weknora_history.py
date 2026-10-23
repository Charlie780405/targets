"""Read-only gates for historical WeKnora evidence projections.

Targets no longer ingests or mutates these projections.  The retained helpers
prevent already revoked or expired source material from re-entering reports or
Vault exports while leaving unrelated legacy events unchanged.
"""

from __future__ import annotations

from sqlalchemy import or_, select
from sqlalchemy.orm import Session
from sqlalchemy.sql.elements import ColumnElement

from packages.domain.models import Event, WeKnoraEvidenceProjection

PROJECTION_ACTIVE = "active"


def weknora_available_clause() -> ColumnElement[bool]:
    """Exclude events bound to a non-active historical WeKnora projection."""

    unavailable = select(WeKnoraEvidenceProjection.event_id).where(
        or_(
            WeKnoraEvidenceProjection.status != PROJECTION_ACTIVE,
            WeKnoraEvidenceProjection.rights_status != "verified",
        ),
        WeKnoraEvidenceProjection.event_id.is_not(None),
    )
    return Event.id.not_in(unavailable)


def is_active_weknora_event(session: Session, event_id: str) -> bool:
    """Keep legacy unbound events visible; block non-active WeKnora history."""

    projection = session.scalar(
        select(WeKnoraEvidenceProjection).where(
            WeKnoraEvidenceProjection.event_id == event_id
        )
    )
    return projection is None or (
        projection.status == PROJECTION_ACTIVE
        and projection.rights_status == "verified"
    )
