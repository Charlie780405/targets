"""发布前为全部事件重算三分数。"""

from __future__ import annotations

from datetime import UTC, date, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from apps.reporter.weekly import _evidences_by_event, _query_prior_events, score_and_update_events
from packages.domain.models import Event


def score_all_events(session: Session, *, reference_date: date | None = None) -> int:
    events = list(session.scalars(select(Event)).all())
    if not events:
        return 0
    ref = reference_date or datetime.now(tz=UTC).date()
    evidences_map = _evidences_by_event(session, [e.id for e in events])
    prior = _query_prior_events(session, ref, target_id=None)
    score_and_update_events(session, events, evidences_map, prior, reference_date=ref)
    session.flush()
    return len(events)
