"""Targets 文献证据浏览器工作台的契约与审核门禁测试。"""

from datetime import date

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from apps.health import create_app
from apps.review_workbench import (
    ReviewConflict,
    apply_review_decision,
    parse_review_decision,
    sanitize_projection_payload,
    serialize_projection,
)
from packages.domain.enums import EventType, MedicalReviewStatus
from packages.domain.models import Event, WeKnoraEvidenceProjection


def _projection(*, status: str = "active") -> WeKnoraEvidenceProjection:
    return WeKnoraEvidenceProjection(
        id="WK-projection-1",
        knowledge_base_id="kb-1",
        artifact_id="artifact-1",
        sha256="a" * 64,
        contract="weknora.targets.approved-evidence",
        contract_version=1,
        title="Evidence title",
        doi="10.1000/example",
        pmid="12345",
        process_status="indexed",
        rights_status="verified",
        status=status,
        event_id="EVT-1",
        payload_json={
            "artifact": {"title": "Evidence title", "file_name": "secret.pdf"},
            "evidence": [{"source_name": "PubMed", "source_url": "https://secret.example"}],
            "pages": [{"page_number": 1, "text_excerpt": "An evidence excerpt."}],
        },
    )


def test_sanitize_projection_payload_keeps_only_evidence_allowlist() -> None:
    payload = {
        "artifact": {
            "title": "Title",
            "doi": "10.1000/example",
            "file_name": "secret.pdf",
            "storage_key": "private/storage/key",
        },
        "evidence": [{"source_name": "PubMed", "source_url": "https://secret.example"}],
        "pages": [{"page_number": 1, "text_excerpt": "Excerpt", "host_path": "/srv/original.pdf"}],
        "download_url": "https://secret.example/download",
    }

    result = sanitize_projection_payload(payload)

    assert result == {
        "artifact": {"title": "Title", "doi": "10.1000/example"},
        "evidence": [{"source_name": "PubMed"}],
        "pages": [{"page_number": 1, "text_excerpt": "Excerpt"}],
    }


def test_parse_review_decision_validates_status_and_reason() -> None:
    assert parse_review_decision({"status": "approved", "reason": "核对完成"}) == (
        MedicalReviewStatus.APPROVED,
        "核对完成",
    )

    with pytest.raises(ValueError, match="status"):
        parse_review_decision({"status": "published", "reason": "不允许"})
    with pytest.raises(ValueError, match="reason"):
        parse_review_decision({"status": "rejected", "reason": ""})


def test_serialize_projection_excludes_internal_fields() -> None:
    projection = _projection()

    result = serialize_projection(projection, review_status=MedicalReviewStatus.PENDING)

    assert result["projection_id"] == "WK-projection-1"
    assert result["review_status"] == "pending"
    assert "file_name" not in str(result)
    assert "storage_key" not in str(result)
    assert "source_url" not in str(result)


def test_serialize_revoked_projection_is_explicitly_not_reviewable() -> None:
    projection = _projection(status="revoked")

    result = serialize_projection(projection, review_status=MedicalReviewStatus.PENDING)

    assert result["status"] == "revoked"
    assert result["reviewable"] is False


def test_review_workbench_lists_sanitized_pending_projection_and_writes_back(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    from packages.domain.database import Base

    Base.metadata.create_all(engine)
    with Session(engine) as session:
        event = Event(
            id="EVT-1",
            event_type=EventType.PUBLICATION,
            event_date=date(2026, 9, 24),
            title="Evidence title",
            medical_review_status=MedicalReviewStatus.PENDING,
            content_hash="b" * 64,
        )
        projection = _projection()
        session.add_all([event, projection])
        session.commit()

    monkeypatch.setenv("TARGETS_REVIEW_UI_ENABLED", "true")
    monkeypatch.setenv("TARGETS_REVIEW_UI_TOKEN", "test-review-token")
    monkeypatch.setenv("TARGETS_REVIEW_UI_KB_ID", "kb-1")
    client = TestClient(create_app(engine))

    page = client.get("/targets/review")
    assert page.status_code == 200
    assert "Targets 文献证据工作台" in page.text
    assert "default-src 'none'" in page.headers["content-security-policy"]

    listing = client.get("/targets/api/projections?status=pending&limit=10")
    assert listing.status_code == 200
    body = listing.json()
    assert body["total"] == 1
    assert body["data"][0]["reviewable"] is True
    assert "source_url" not in listing.text
    assert "storage_key" not in listing.text

    unauthorized = client.patch(
        "/targets/api/projections/WK-projection-1/review",
        json={"status": "approved", "reason": "核对完成"},
    )
    assert unauthorized.status_code == 401

    reviewed = client.patch(
        "/targets/api/projections/WK-projection-1/review",
        headers={"Authorization": "Bearer test-review-token"},
        json={"status": "approved", "reason": "核对完成"},
    )
    assert reviewed.status_code == 200
    with Session(engine) as session:
        refreshed = session.get(Event, "EVT-1")
        assert refreshed is not None
        assert refreshed.medical_review_status == MedicalReviewStatus.APPROVED


def test_review_workbench_is_disabled_by_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("TARGETS_REVIEW_UI_ENABLED", raising=False)
    monkeypatch.delenv("TARGETS_REVIEW_UI_KB_ID", raising=False)
    client = TestClient(create_app(create_engine("sqlite:///:memory:")))

    response = client.get("/targets/review")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "REVIEW_UI_DISABLED"


def test_revoked_projection_cannot_be_reviewed() -> None:
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    from packages.domain.database import Base

    Base.metadata.create_all(engine)
    with Session(engine) as session:
        session.add(
            Event(
                id="EVT-1",
                event_type=EventType.PUBLICATION,
                event_date=date(2026, 9, 24),
                title="Evidence title",
                medical_review_status=MedicalReviewStatus.PENDING,
                content_hash="b" * 64,
            )
        )
        session.add(_projection(status="revoked"))
        session.commit()

        with pytest.raises(ReviewConflict, match="revoked"):
            apply_review_decision(
                session,
                "WK-projection-1",
                {"status": "approved", "reason": "不应写回"},
                knowledge_base_id="kb-1",
            )
