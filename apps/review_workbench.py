"""WeKnora 证据投影的内网浏览与人工审核门禁。

该模块只返回投影白名单字段，不读取或输出 WeKnora 原件、存储键、源 URL
或宿主机路径。页面由 health 服务回环端口提供，不能替代 WeKnora 的事实源。
"""

from __future__ import annotations

import hmac
import logging
import os
from collections.abc import Mapping
from datetime import datetime
from typing import Any

from fastapi import Request
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from apps.collector.weknora_literature import is_active_weknora_event
from packages.domain.enums import MedicalReviewStatus
from packages.domain.models import Event, WeKnoraEvidenceProjection

LOGGER = logging.getLogger(__name__)
PROJECTION_ACTIVE = "active"
PROJECTION_REVOKED = "revoked"
_MAX_REASON_LENGTH = 2_000
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


class ReviewConflict(ValueError):
    """投影已撤销、缺少关联事件或不再满足审核门禁。"""


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


def parse_review_decision(payload: Mapping[str, Any] | object) -> tuple[MedicalReviewStatus, str]:
    """校验浏览器审核输入；理由不进入证据投影或 WeKnora 原件。"""

    source = _safe_mapping(payload)
    raw_status = source.get("status")
    if not isinstance(raw_status, str):
        raise TypeError("status 必须是字符串")
    try:
        status = MedicalReviewStatus(raw_status.strip().lower())
    except ValueError as exc:
        raise ValueError("status 不是受支持的审核状态") from exc
    reason = _safe_string(source.get("reason"), limit=_MAX_REASON_LENGTH)
    if not reason:
        raise ValueError("reason 不能为空")
    return status, reason


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
        "reviewable": projection.status == PROJECTION_ACTIVE and bool(projection.event_id),
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


def apply_review_decision(
    session: Session,
    projection_id: str,
    payload: Mapping[str, Any] | object,
    *,
    knowledge_base_id: str,
) -> tuple[dict[str, Any], str]:
    """将人工决定写回关联事件，拒绝 revoked/孤儿投影。"""

    status, reason = parse_review_decision(payload)
    projection = session.get(WeKnoraEvidenceProjection, projection_id)
    if projection is None:
        raise LookupError("投影不存在")
    if projection.knowledge_base_id != knowledge_base_id:
        raise LookupError("投影不存在")
    if projection.status != PROJECTION_ACTIVE:
        raise ReviewConflict("revoked 投影不可审核")
    if not projection.event_id:
        raise ReviewConflict("投影缺少关联审核事件")
    event = session.get(Event, projection.event_id)
    if event is None or not is_active_weknora_event(session, event.id):
        raise ReviewConflict("关联事件不可审核")
    event.medical_review_status = status
    session.flush()
    LOGGER.info(
        "Targets 文献审核写回：projection=%s status=%s reason_length=%d",
        projection.id,
        status.value,
        len(reason),
    )
    return serialize_projection(projection, review_status=status), reason


def _review_ui_enabled() -> bool:
    return os.getenv("TARGETS_REVIEW_UI_ENABLED", "false").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


def _review_ui_kb_id() -> str:
    return (
        os.getenv("TARGETS_REVIEW_UI_KB_ID", "").strip()
        or os.getenv("WEKNORA_TARGETS_KB_ID", "").strip()
    )


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


def _has_review_token(request: Any) -> bool:
    expected = os.getenv("TARGETS_REVIEW_UI_TOKEN", "")
    supplied = request.headers.get("authorization", "")
    if not expected or not supplied.startswith("Bearer "):
        return False
    return hmac.compare_digest(supplied[7:], expected)


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

    @router.patch("/targets/api/projections/{projection_id}/review")
    async def review_projection(request: Request, projection_id: str) -> Any:
        unavailable_response = unavailable()
        if unavailable_response is not None:
            return unavailable_response
        if not _has_review_token(request):
            return _error_response("UNAUTHORIZED", "审核令牌无效或未配置", 401)
        try:
            payload = await request.json()
            if not isinstance(payload, Mapping):
                raise TypeError("请求体必须是 JSON 对象")
            with Session(bind=bind) as session:
                data, _reason = apply_review_decision(
                    session,
                    projection_id,
                    payload,
                    knowledge_base_id=_review_ui_kb_id(),
                )
                session.commit()
            return JSONResponse({"data": data}, headers=_security_headers())
        except LookupError as exc:
            return _error_response("NOT_FOUND", str(exc), 404)
        except ReviewConflict as exc:
            return _error_response("REVIEW_CONFLICT", str(exc), 409)
        except (TypeError, ValueError) as exc:
            return _error_response("VALIDATION_ERROR", str(exc), 422)

    return router
