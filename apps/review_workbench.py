"""WeKnora 历史证据投影的内网只读浏览器。

该模块只返回投影白名单字段，不读取或输出 WeKnora 原件、存储键、源 URL
或宿主机路径。页面由 health 服务回环端口提供，不能替代 WeKnora 的事实源。
"""

from __future__ import annotations

import os
from collections.abc import Mapping
from datetime import datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from packages.domain.enums import MedicalReviewStatus
from packages.domain.models import Event, WeKnoraEvidenceProjection

PROJECTION_ACTIVE = "active"
PROJECTION_REVOKED = "revoked"
_MAX_EXCERPT_LENGTH = 4_000
_MAX_LIST_ITEMS = 100
_ARTIFACT_FIELDS = frozenset({"title", "doi", "pmid", "pmcid", "process_status", "rights_status"})
_EVIDENCE_FIELDS = frozenset(
    {"source_name", "license_basis", "rights_valid_until", "evidence_hash"}
)
_PAGE_FIELDS = frozenset(
    {"page_number", "status", "citation_locator", "text_excerpt", "text_sha256"}
)
_ANCHOR_FIELDS = frozenset({"kind", "label", "excerpt"})


def _safe_string(value: object, *, limit: int = _MAX_EXCERPT_LENGTH) -> str | None:
    if not isinstance(value, str):
        return None
    value = value.strip()
    return value[:limit] if value else None


def _safe_mapping(value: object) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _pick_fields(value: object, allowed: frozenset[str]) -> dict[str, Any]:
    source = _safe_mapping(value)
    result: dict[str, Any] = {}
    for key in allowed:
        if key not in source:
            continue
        if key == "page_number":
            page_number = source[key]
            if isinstance(page_number, int) and 1 <= page_number <= 100_000:
                result[key] = page_number
            continue
        safe_value = _safe_string(source[key])
        if safe_value is not None:
            result[key] = safe_value
    return result


def sanitize_projection_payload(payload: Mapping[str, Any] | object) -> dict[str, Any]:
    """从 WeKnora 投影中提取浏览器所需的最小证据字段。"""

    source = _safe_mapping(payload)
    result: dict[str, Any] = {}
    artifact = _pick_fields(source.get("artifact"), _ARTIFACT_FIELDS)
    if artifact:
        result["artifact"] = artifact

    evidence_rows = source.get("evidence")
    if isinstance(evidence_rows, list):
        evidence: list[dict[str, Any]] = []
        for row in evidence_rows[:_MAX_LIST_ITEMS]:
            picked = _pick_fields(row, _EVIDENCE_FIELDS)
            if picked:
                evidence.append(picked)
        result["evidence"] = evidence

    page_rows = source.get("pages")
    if isinstance(page_rows, list):
        pages: list[dict[str, Any]] = []
        for row in page_rows[:_MAX_LIST_ITEMS]:
            page = _pick_fields(row, _PAGE_FIELDS)
            anchors = _safe_mapping(row).get("anchors")
            if isinstance(anchors, list):
                safe_anchors: list[dict[str, Any]] = []
                for anchor in anchors[:_MAX_LIST_ITEMS]:
                    picked = _pick_fields(anchor, _ANCHOR_FIELDS)
                    if picked:
                        safe_anchors.append(picked)
                page["anchors"] = safe_anchors
            if page:
                pages.append(page)
        result["pages"] = pages
    return result


def _iso(value: datetime | None) -> str | None:
    return value.isoformat() if value else None


def serialize_projection(
    projection: WeKnoraEvidenceProjection,
    *,
    review_status: MedicalReviewStatus | str | None,
) -> dict[str, Any]:
    """生成浏览器响应，明确标记 revoked 且不暴露关联内部 ID。"""

    review_value = (
        review_status.value if isinstance(review_status, MedicalReviewStatus) else review_status
    )
    return {
        "projection_id": projection.id,
        "knowledge_base_id": projection.knowledge_base_id,
        "artifact_id": projection.artifact_id,
        "sha256": projection.sha256,
        "contract": projection.contract,
        "contract_version": projection.contract_version,
        "title": projection.title,
        "doi": projection.doi,
        "pmid": projection.pmid,
        "process_status": projection.process_status,
        "rights_status": projection.rights_status,
        "status": projection.status,
        "review_status": review_value,
        "reviewable": False,
        "first_seen_at": _iso(projection.first_seen_at),
        "last_seen_at": _iso(projection.last_seen_at),
        "payload": sanitize_projection_payload(projection.payload_json),
    }


def list_projection_rows(
    session: Session,
    *,
    knowledge_base_id: str,
    status: str,
    limit: int,
    offset: int,
) -> tuple[list[dict[str, Any]], int]:
    """分页返回 active/revoked 投影；pending 只表示 Targets 待审事件。"""

    if status not in {"pending", "all", PROJECTION_ACTIVE, PROJECTION_REVOKED}:
        raise ValueError("status 必须是 pending、all、active 或 revoked")
    if not 1 <= limit <= 100 or offset < 0:
        raise ValueError("分页参数无效")

    statement = select(WeKnoraEvidenceProjection, Event.medical_review_status).join(
        Event,
        WeKnoraEvidenceProjection.event_id == Event.id,
        isouter=True,
    )
    statement = statement.where(WeKnoraEvidenceProjection.knowledge_base_id == knowledge_base_id)
    if status == "pending":
        statement = statement.where(
            WeKnoraEvidenceProjection.status == PROJECTION_ACTIVE,
            Event.medical_review_status == MedicalReviewStatus.PENDING,
        )
    elif status in {PROJECTION_ACTIVE, PROJECTION_REVOKED}:
        statement = statement.where(WeKnoraEvidenceProjection.status == status)

    rows = list(
        session.execute(
            statement.order_by(WeKnoraEvidenceProjection.updated_at.desc())
            .offset(offset)
            .limit(limit)
        ).all()
    )
    # Count from the same filtered query without exposing unbounded rows to the API.
    count_statement = (
        select(func.count())
        .select_from(WeKnoraEvidenceProjection)
        .join(
            Event,
            WeKnoraEvidenceProjection.event_id == Event.id,
            isouter=True,
        )
    )
    count_statement = count_statement.where(
        WeKnoraEvidenceProjection.knowledge_base_id == knowledge_base_id
    )
    if status == "pending":
        count_statement = count_statement.where(
            WeKnoraEvidenceProjection.status == PROJECTION_ACTIVE,
            Event.medical_review_status == MedicalReviewStatus.PENDING,
        )
    elif status in {PROJECTION_ACTIVE, PROJECTION_REVOKED}:
        count_statement = count_statement.where(WeKnoraEvidenceProjection.status == status)
    total_count = int(session.scalar(count_statement) or 0)
    serialized = [
        serialize_projection(projection, review_status=review_status)
        for projection, review_status in rows
    ]
    return serialized, total_count


def _review_ui_enabled() -> bool:
    return os.getenv("TARGETS_REVIEW_UI_ENABLED", "false").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


def _review_ui_kb_id() -> str:
    return os.getenv("TARGETS_REVIEW_UI_KB_ID", "").strip()


def _security_headers() -> dict[str, str]:
    return {
        "Cache-Control": "no-store",
        "X-Content-Type-Options": "nosniff",
        "X-Frame-Options": "DENY",
        "Referrer-Policy": "no-referrer",
        "Content-Security-Policy": (
            "default-src 'none'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; "
            "connect-src 'self'; base-uri 'none'; form-action 'self'"
        ),
    }


def _error_response(code: str, message: str, status_code: int) -> Any:
    from fastapi.responses import JSONResponse

    return JSONResponse(
        {"error": {"code": code, "message": message}},
        status_code=status_code,
        headers=_security_headers(),
    )


def create_review_router(engine: Any) -> Any:
    """创建受 feature flag 控制的 Targets 浏览器工作台路由。"""

    from fastapi import APIRouter
    from fastapi.responses import HTMLResponse, JSONResponse

    from apps.review_workbench_ui import REVIEW_WORKBENCH_HTML

    router = APIRouter()
    if engine is None:
        from packages.domain.database import engine as default_engine

        bind = default_engine
    else:
        bind = engine

    def unavailable() -> Any:
        if not _review_ui_enabled():
            return _error_response("REVIEW_UI_DISABLED", "Targets 文献工作台未启用", 404)
        if not _review_ui_kb_id():
            return _error_response("REVIEW_UI_KB_NOT_CONFIGURED", "Targets 工作台未绑定 KB", 503)
        return None

    @router.get("/targets/review", response_class=HTMLResponse)
    def review_page() -> Any:
        unavailable_response = unavailable()
        if unavailable_response is not None:
            return unavailable_response
        return HTMLResponse(REVIEW_WORKBENCH_HTML, headers=_security_headers())

    @router.get("/targets/api/projections")
    def list_projections(status: str = "pending", limit: int = 50, offset: int = 0) -> Any:
        unavailable_response = unavailable()
        if unavailable_response is not None:
            return unavailable_response
        try:
            with Session(bind=bind) as session:
                data, total = list_projection_rows(
                    session,
                    knowledge_base_id=_review_ui_kb_id(),
                    status=status,
                    limit=limit,
                    offset=offset,
                )
            return JSONResponse(
                {"data": data, "total": total, "limit": limit, "offset": offset},
                headers=_security_headers(),
            )
        except ValueError as exc:
            return _error_response("VALIDATION_ERROR", str(exc), 422)

    return router
