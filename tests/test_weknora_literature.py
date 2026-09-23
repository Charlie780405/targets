"""WeKnora 文献证据接收端的契约、幂等与撤销回归。"""

from __future__ import annotations

from datetime import UTC, datetime

import httpx
import pytest
from sqlalchemy import select

from apps.collector.weknora_literature import (
    PullError,
    WeKnoraClient,
    WeKnoraCollection,
    sync_collection,
)
from apps.reporter.publish import should_export_to_vault
from packages.domain.enums import EvidenceLevel, MedicalReviewStatus
from packages.domain.models import Event, SourceDocument, WeKnoraEvidenceProjection


def evidence_row(artifact_id: str, *, sha256: str = "a" * 64) -> dict[str, object]:
    return {
        "contract": "weknora.targets.approved-evidence",
        "version": 1,
        "exported_at": "2026-09-24T00:00:00Z",
        "artifact": {
            "artifact_id": artifact_id,
            "doi": "10.1000/example",
            "pmid": "12345678",
            "title": "Approved evidence title",
            "sha256": sha256,
            "file_name": "evidence.pdf",
            "parser_engine": "docreader",
            "parser_version": "test",
            "rights_status": "verified",
            "rights_statement": "enterprise subscription",
            "process_status": "indexed",
        },
        "evidence": [
            {
                "source_name": "PubMed",
                "license_basis": "open access",
                "evidence_hash": "b" * 64,
            }
        ],
        "pages": [
            {
                "page_number": 1,
                "status": "parsed",
                "text_sha256": "c" * 64,
                "text_excerpt": "Primary endpoint was met.",
                "anchors": [],
            }
        ],
    }


def collection(*rows: dict[str, object]) -> WeKnoraCollection:
    return WeKnoraCollection.model_validate(
        {
            "contract": "weknora.targets.approved-evidence.collection",
            "version": 1,
            "exported_at": "2026-09-24T00:00:00Z",
            "data": list(rows),
            "total": len(rows),
            "limit": 100,
            "offset": 0,
        }
    )


def test_client_pulls_paginated_contract_and_keeps_key_out_of_payload() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        query = dict(request.url.params)
        offset = int(query["offset"])
        rows = [evidence_row("artifact-1")] if offset == 0 else []
        return httpx.Response(
            200,
            json={
                "contract": "weknora.targets.approved-evidence.collection",
                "version": 1,
                "exported_at": "2026-09-24T00:00:00Z",
                "data": rows,
                "total": 1,
                "limit": 100,
                "offset": offset,
            },
        )

    with WeKnoraClient(
        "https://weknora.example",
        "test-only-key",
        transport=httpx.MockTransport(handler),
    ) as client:
        result = client.pull_collection("kb-1")

    assert result.total == 1
    assert result.data[0].artifact.artifact_id == "artifact-1"
    assert all(request.headers["x-api-key"] == "test-only-key" for request in requests)
    assert "test-only-key" not in result.model_dump_json()


def test_client_rejects_forbidden_fields_and_redirects() -> None:
    forbidden = evidence_row("artifact-1")
    artifact = forbidden["artifact"]
    assert isinstance(artifact, dict)
    artifact["storage_key"] = "private/path"

    def forbidden_handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "contract": "weknora.targets.approved-evidence.collection",
                "version": 1,
                "exported_at": "2026-09-24T00:00:00Z",
                "data": [forbidden],
                "total": 1,
                "limit": 100,
                "offset": 0,
            },
        )

    with WeKnoraClient(
        "https://weknora.example",
        "test-only-key",
        transport=httpx.MockTransport(forbidden_handler),
    ) as client, pytest.raises(PullError, match="禁止交换"):
        client.fetch_page("kb-1", limit=100, offset=0)

    with WeKnoraClient(
        "https://weknora.example",
        "test-only-key",
        transport=httpx.MockTransport(lambda _request: httpx.Response(302, headers={"location": "https://other.example"})),
    ) as client, pytest.raises(PullError, match="重定向"):
        client.fetch_page("kb-1", limit=100, offset=0)


def test_sync_is_idempotent_and_creates_pending_projection(session) -> None:  # type: ignore[no-untyped-def]
    now = datetime(2026, 9, 24, tzinfo=UTC)
    first = sync_collection(session, "kb-1", collection(evidence_row("artifact-1")), now=now)
    second = sync_collection(session, "kb-1", collection(evidence_row("artifact-1")), now=now)
    session.commit()

    assert first.created == 1
    assert second.unchanged == 1
    assert session.scalar(select(WeKnoraEvidenceProjection).where(WeKnoraEvidenceProjection.knowledge_base_id == "kb-1")) is not None
    projection = session.scalar(select(WeKnoraEvidenceProjection))
    assert projection is not None
    assert projection.status == "active"
    assert projection.event_id is not None
    event = session.get(Event, projection.event_id)
    assert event is not None
    assert event.medical_review_status == MedicalReviewStatus.PENDING
    assert session.scalar(select(Event).where(Event.id == projection.event_id)) is not None
    assert session.scalar(select(SourceDocument).where(SourceDocument.id == projection.source_document_id)) is not None
    assert len(list(session.scalars(select(Event)))) == 1
    source_document = session.get(SourceDocument, projection.source_document_id)
    assert source_document is not None
    assert source_document.source_url == "https://doi.org/10.1000/example"


def test_sync_marks_missing_projection_revoked_and_does_not_delete_audit(session) -> None:  # type: ignore[no-untyped-def]
    now = datetime(2026, 9, 24, tzinfo=UTC)
    sync_collection(session, "kb-1", collection(evidence_row("artifact-1")), now=now)
    result = sync_collection(session, "kb-1", collection(), now=now)
    session.commit()

    projection = session.scalar(select(WeKnoraEvidenceProjection))
    assert projection is not None
    assert result.revoked == 1
    assert projection.status == "revoked"
    assert projection.revoked_at == now.replace(tzinfo=None)
    assert session.get(Event, projection.event_id) is not None


def test_revoked_projection_cannot_reenter_vault_export(session) -> None:  # type: ignore[no-untyped-def]
    now = datetime(2026, 9, 24, tzinfo=UTC)
    sync_collection(session, "kb-1", collection(evidence_row("artifact-1")), now=now)
    sync_collection(session, "kb-1", collection(), now=now)
    event = session.scalar(select(Event))
    assert event is not None

    assert should_export_to_vault(
        session,
        event,
        [],
        review_queue_ids={event.id},
        min_importance=None,
        min_relevance=0.0,
    ) is False


def test_reactivated_projection_requires_review_again(session) -> None:  # type: ignore[no-untyped-def]
    now = datetime(2026, 9, 24, tzinfo=UTC)
    row = evidence_row("artifact-1")
    sync_collection(session, "kb-1", collection(row), now=now)
    projection = session.scalar(select(WeKnoraEvidenceProjection))
    assert projection is not None
    event = session.get(Event, projection.event_id)
    assert event is not None
    event.medical_review_status = MedicalReviewStatus.APPROVED
    session.flush()

    sync_collection(session, "kb-1", collection(), now=now)
    result = sync_collection(session, "kb-1", collection(row), now=now)
    session.commit()

    assert result.updated == 1
    assert projection.status == "active"
    assert event.medical_review_status == MedicalReviewStatus.PENDING


def test_unknown_source_is_conservative_and_traceable(session) -> None:  # type: ignore[no-untyped-def]
    row = evidence_row("artifact-unknown")
    artifact = row["artifact"]
    assert isinstance(artifact, dict)
    artifact["doi"] = None
    artifact["pmid"] = None
    artifact["pmcid"] = None
    row["evidence"] = [{
        "source_name": "Enterprise archive",
        "license_basis": "internal authorization",
        "evidence_hash": "d" * 64,
    }]
    sync_collection(session, "kb-1", collection(row))
    projection = session.scalar(select(WeKnoraEvidenceProjection))
    assert projection is not None
    event = session.get(Event, projection.event_id)
    assert event is not None
    evidence = event.evidences[0]
    assert evidence.evidence_level == EvidenceLevel.E
    source_document = session.get(SourceDocument, projection.source_document_id)
    assert source_document is not None
    assert source_document.source_url.startswith("weknora://")
