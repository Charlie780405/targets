"""WeKnora 批准文献证据的受控拉取与 Targets 待审投影。"""

from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path
from typing import Any, Self
from urllib.parse import quote, urlsplit

import httpx
from pydantic import BaseModel, ConfigDict, Field, ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from packages.domain.enums import EventType, EvidenceLevel, MedicalReviewStatus
from packages.domain.models import (
    Event,
    Evidence,
    Publication,
    SourceDocument,
    WeKnoraEvidenceProjection,
)
from packages.entity_resolution.dedup import normalize_doi

CONTRACT = "weknora.targets.approved-evidence.collection"
ITEM_CONTRACT = "weknora.targets.approved-evidence"
VERSION = 1
PROJECTION_ACTIVE = "active"
PROJECTION_REVOKED = "revoked"
MAX_PAGE_BYTES = 16 * 1024 * 1024
MAX_EXCERPT_CHARS = 12_000
FORBIDDEN_KEYS = frozenset(
    {"storage_key", "original_ref", "source_url", "download_url", "host_path"}
)


class PullError(RuntimeError):
    """可安全展示给运维人员的拉取错误，不包含响应正文或 API Key。"""


class WeKnoraArtifact(BaseModel):
    model_config = ConfigDict(extra="ignore")

    artifact_id: str = Field(min_length=1, max_length=64)
    doi: str | None = None
    pmid: str | None = None
    pmcid: str | None = None
    title: str | None = None
    sha256: str = Field(pattern=r"^[0-9a-fA-F]{64}$")
    file_name: str | None = None
    parser_engine: str | None = None
    parser_version: str | None = None
    rights_status: str
    rights_statement: str | None = None
    process_status: str


class WeKnoraEvidence(BaseModel):
    model_config = ConfigDict(extra="ignore")

    source_name: str
    license_basis: str
    evidence_hash: str = Field(pattern=r"^[0-9a-fA-F]{64}$")
    rights_valid_until: datetime | None = None


class WeKnoraPage(BaseModel):
    model_config = ConfigDict(extra="ignore")

    page_number: int = Field(ge=1)
    status: str
    citation_locator: str | None = None
    text_sha256: str | None = Field(default=None, pattern=r"^[0-9a-fA-F]{64}$")
    text_excerpt: str | None = None
    anchors: list[dict[str, Any]] = Field(default_factory=list)


class WeKnoraEvidenceExport(BaseModel):
    model_config = ConfigDict(extra="ignore")

    contract: str
    version: int
    exported_at: datetime
    artifact: WeKnoraArtifact
    evidence: list[WeKnoraEvidence] = Field(default_factory=list)
    pages: list[WeKnoraPage] = Field(default_factory=list)


class WeKnoraCollection(BaseModel):
    model_config = ConfigDict(extra="ignore")

    contract: str
    version: int
    exported_at: datetime
    data: list[WeKnoraEvidenceExport]
    total: int = Field(ge=0)
    limit: int = Field(ge=1, le=100)
    offset: int = Field(ge=0)


@dataclass(frozen=True)
class SyncStats:
    created: int = 0
    updated: int = 0
    unchanged: int = 0
    revoked: int = 0


def _validate_base_url(value: str) -> str:
    parsed = urlsplit(value)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise PullError("WeKnora base URL 必须是带主机名的 HTTP(S) 地址")
    if parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise PullError("WeKnora base URL 不得包含用户信息、查询参数或片段")
    return value.rstrip("/")


def read_api_key(*, env_name: str, file_path: Path | None = None) -> str:
    """从环境变量或 owner-only 文件读取 API Key，不返回任何日志信息。"""

    if file_path is not None:
        try:
            value = file_path.read_text(encoding="utf-8").strip()
        except OSError as exc:
            raise PullError("无法读取 WeKnora API Key 文件") from exc
    else:
        value = os.environ.get(env_name, "").strip()
    if not value or any(char.isspace() for char in value):
        raise PullError("WeKnora API Key 必须来自非空且不含空白的环境变量或文件")
    return value


def _reject_forbidden_keys(value: Any) -> None:
    if isinstance(value, dict):
        if FORBIDDEN_KEYS.intersection(value):
            raise PullError("WeKnora 证据响应包含禁止交换的内部存储字段")
        for child in value.values():
            _reject_forbidden_keys(child)
    elif isinstance(value, list):
        for child in value:
            _reject_forbidden_keys(child)


def _parse_page(payload: object, *, limit: int, offset: int) -> WeKnoraCollection:
    if not isinstance(payload, dict):
        raise PullError("WeKnora 证据集合不是 JSON 对象")
    _reject_forbidden_keys(payload)
    try:
        page = WeKnoraCollection.model_validate(payload)
    except ValidationError as exc:
        raise PullError("WeKnora 证据集合字段无效") from exc
    if page.contract != CONTRACT or page.version != VERSION:
        raise PullError("WeKnora 证据集合契约或版本不匹配")
    if page.limit != limit or page.offset != offset:
        raise PullError("WeKnora 证据集合分页游标与请求不一致")
    if len(page.data) > limit:
        raise PullError("WeKnora 返回条数超过请求上限")
    for row in page.data:
        if row.contract != ITEM_CONTRACT or row.version != VERSION:
            raise PullError("WeKnora 证据条目契约或版本无效")
        artifact = row.artifact
        if artifact.rights_status != "verified" or artifact.process_status not in {"approved", "indexed"}:
            raise PullError("WeKnora 返回了不满足发布状态门禁的证据条目")
    return page


class WeKnoraClient:
    """只读 WeKnora 客户端；API Key 只进入请求头，不进入日志和落库投影。"""

    def __init__(
        self,
        base_url: str,
        api_key: str,
        *,
        timeout: float = 30.0,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        if not api_key.strip() or any(char.isspace() for char in api_key):
            raise PullError("WeKnora API Key 必须是非空且不含空白的值")
        if timeout <= 0:
            raise PullError("WeKnora 请求 timeout 必须大于 0")
        self.base_url = _validate_base_url(base_url)
        self._client = httpx.Client(
            base_url=self.base_url,
            headers={"Accept": "application/json", "X-API-Key": api_key},
            follow_redirects=False,
            timeout=timeout,
            transport=transport,
        )

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *_args: object) -> None:
        self.close()

    def close(self) -> None:
        self._client.close()

    def fetch_page(self, knowledge_base_id: str, *, limit: int, offset: int) -> WeKnoraCollection:
        if not knowledge_base_id.strip():
            raise PullError("WeKnora KB ID 不能为空")
        if not 1 <= limit <= 100 or offset < 0:
            raise PullError("WeKnora 分页参数无效")
        path = f"/api/v1/knowledge-bases/{quote(knowledge_base_id, safe='')}"
        path += f"/literature/targets-evidence?limit={limit}&offset={offset}"
        try:
            response = self._client.get(path)
        except httpx.HTTPError as exc:
            raise PullError("无法连接 WeKnora 文献证据接口") from exc
        if 300 <= response.status_code < 400:
            raise PullError("WeKnora 证据接口不允许 HTTP 重定向")
        if response.status_code < 200 or response.status_code >= 300:
            raise PullError(f"WeKnora 返回 HTTP {response.status_code}，请检查 API Key 和 KB 权限")
        if len(response.content) > MAX_PAGE_BYTES:
            raise PullError("WeKnora 证据分页响应超过 16 MiB 上限")
        try:
            payload = response.json()
        except (ValueError, UnicodeDecodeError) as exc:
            raise PullError("WeKnora 返回的证据不是有效 JSON") from exc
        return _parse_page(payload, limit=limit, offset=offset)

    def pull_collection(self, knowledge_base_id: str, *, page_size: int = 100) -> WeKnoraCollection:
        if not 1 <= page_size <= 100:
            raise PullError("WeKnora page_size 必须在 1 到 100 之间")
        rows: list[WeKnoraEvidenceExport] = []
        offset = 0
        expected_total: int | None = None
        exported_at: datetime | None = None
        while expected_total is None or offset < expected_total:
            page = self.fetch_page(knowledge_base_id, limit=page_size, offset=offset)
            if expected_total is None:
                expected_total = page.total
                exported_at = page.exported_at
            elif page.total != expected_total:
                raise PullError("拉取期间 WeKnora total 发生变化，请重新执行同步")
            if not page.data:
                if offset != expected_total:
                    raise PullError("WeKnora 分页提前结束，未能完整拉取证据集合")
                break
            rows.extend(page.data)
            offset += len(page.data)
            if offset > expected_total:
                raise PullError("WeKnora 分页结果超过 total")
        if expected_total is None or len(rows) != expected_total:
            raise PullError("WeKnora 拉取结果数量与 total 不一致")
        assert exported_at is not None
        return WeKnoraCollection(
            contract=CONTRACT,
            version=VERSION,
            exported_at=exported_at,
            data=rows,
            total=len(rows),
            limit=page_size,
            offset=0,
        )


def _projection_id(knowledge_base_id: str, artifact_id: str) -> str:
    digest = sha256(f"{knowledge_base_id}\0{artifact_id}".encode()).hexdigest()
    # 3 字节前缀 + 61 个十六进制字符，严格落在现有 String(64) 主键边界内。
    return f"WK-{digest[:61]}"


def _event_id(projection_id: str) -> str:
    return projection_id[:32]


def _publication_id(projection_id: str) -> str:
    return f"WK-PUB-{projection_id[3:]}"[:64]


def _source_document_id(projection_id: str) -> str:
    return f"WK-SDOC-{projection_id[3:]}"[:64]


def _evidence_id(projection_id: str) -> str:
    return f"WK-EVD-{projection_id[3:]}"[:64]


def _excerpt(row: WeKnoraEvidenceExport) -> str | None:
    parts = [page.text_excerpt.strip() for page in row.pages if page.text_excerpt and page.text_excerpt.strip()]
    if not parts:
        return None
    return "\n\n".join(parts)[:MAX_EXCERPT_CHARS]


def _source_url(knowledge_base_id: str, artifact: WeKnoraArtifact) -> str:
    if artifact.doi:
        return f"https://doi.org/{quote(normalize_doi(artifact.doi) or artifact.doi, safe='/')}"
    if artifact.pmid:
        return f"https://pubmed.ncbi.nlm.nih.gov/{quote(artifact.pmid, safe='')}/"
    if artifact.pmcid:
        return f"https://pmc.ncbi.nlm.nih.gov/articles/{quote(artifact.pmcid, safe='')}/"
    return f"weknora://{quote(knowledge_base_id, safe='')}/artifact/{quote(artifact.artifact_id, safe='')}"


def _first_source(row: WeKnoraEvidenceExport) -> str:
    if row.evidence and row.evidence[0].source_name.strip():
        return row.evidence[0].source_name.strip()[:100]
    return "approved-evidence"


def _evidence_level(row: WeKnoraEvidenceExport) -> EvidenceLevel:
    """按交换包中的可验证文献来源保守映射证据等级。"""

    source_names = " ".join(item.source_name.lower() for item in row.evidence)
    if any(name in source_names for name in ("pubmed", "pmc", "europe pmc")):
        return EvidenceLevel.B
    return EvidenceLevel.E


def _upsert_projection(
    session: Session,
    knowledge_base_id: str,
    row: WeKnoraEvidenceExport,
    now: datetime,
) -> tuple[str, str]:
    artifact = row.artifact
    projection_id = _projection_id(knowledge_base_id, artifact.artifact_id)
    source_document_id = _source_document_id(projection_id)
    event_id = _event_id(projection_id)
    evidence_id = _evidence_id(projection_id)
    title = (artifact.title or artifact.file_name or artifact.artifact_id).strip()[:10_000]
    excerpt = _excerpt(row)
    doi = normalize_doi(artifact.doi)
    source_name = f"WeKnora/{_first_source(row)}"[:128]
    source_url = _source_url(knowledge_base_id, artifact)
    payload = row.model_dump(mode="json")

    source_document = session.get(SourceDocument, source_document_id)
    if source_document is None:
        source_document = SourceDocument(
            id=source_document_id,
            source_id=projection_id,
            source_name=source_name,
            source_url=source_url,
            title=title,
            fetched_at=now,
            content_hash=artifact.sha256,
            payload_json=payload,
        )
        session.add(source_document)
    else:
        source_document.source_name = source_name
        source_document.title = title
        source_document.fetched_at = now
        source_document.content_hash = artifact.sha256
        source_document.payload_json = payload

    publication: Publication | None = None
    if doi:
        publication = session.scalar(select(Publication).where(Publication.doi == doi))
    if publication is None and artifact.pmid:
        publication = session.scalar(select(Publication).where(Publication.pmid == artifact.pmid))
    if publication is None:
        publication = session.get(Publication, _publication_id(projection_id))
    if publication is None:
        publication = Publication(
            id=_publication_id(projection_id),
            pmid=artifact.pmid,
            doi=doi,
            title=title,
            abstract=excerpt,
            published_at=None,
            retracted=False,
            content_hash=artifact.sha256,
        )
        session.add(publication)
    elif publication.id.startswith("WK-PUB-"):
        publication.title = title
        publication.abstract = excerpt
        publication.content_hash = artifact.sha256

    event = session.get(Event, event_id)
    previous_hash = event.content_hash if event is not None else None
    if event is None:
        event = Event(
            id=event_id,
            event_type=EventType.PUBLICATION,
            event_date=now.date(),
            discovered_at=now,
            title=title,
            summary=(
                f"weknora_import=approved; artifact_id={artifact.artifact_id}; "
                "review_required=true; source_quality=unclassified"
            ),
            medical_review_status=MedicalReviewStatus.PENDING,
            source_count=1,
            content_hash=artifact.sha256,
        )
        session.add(event)
    else:
        event.title = title
        event.content_hash = artifact.sha256
        if previous_hash and previous_hash != artifact.sha256:
            event.medical_review_status = MedicalReviewStatus.PENDING

    evidence = session.get(Evidence, evidence_id)
    if evidence is None:
        session.add(
            Evidence(
                id=evidence_id,
                event_id=event_id,
                source_document_id=source_document_id,
                source_name=source_name,
                source_url=source_url,
                evidence_snippet=excerpt[:2_000] if excerpt else None,
                evidence_level=_evidence_level(row),
                published_at=None,
                fetched_at=now,
                content_hash=artifact.sha256,
            )
        )
    else:
        evidence.source_document_id = source_document_id
        evidence.source_name = source_name
        evidence.source_url = source_url
        evidence.evidence_snippet = excerpt[:2_000] if excerpt else None
        evidence.fetched_at = now
        evidence.content_hash = artifact.sha256

    projection = session.scalar(
        select(WeKnoraEvidenceProjection).where(
            WeKnoraEvidenceProjection.knowledge_base_id == knowledge_base_id,
            WeKnoraEvidenceProjection.artifact_id == artifact.artifact_id,
        )
    )
    if projection is None:
        projection = WeKnoraEvidenceProjection(
            id=projection_id,
            knowledge_base_id=knowledge_base_id,
            artifact_id=artifact.artifact_id,
            sha256=artifact.sha256,
            contract=row.contract,
            contract_version=row.version,
            title=title,
            doi=doi,
            pmid=artifact.pmid,
            process_status=artifact.process_status,
            rights_status=artifact.rights_status,
            status=PROJECTION_ACTIVE,
            source_document_id=source_document_id,
            event_id=event_id,
            payload_json=payload,
            first_seen_at=now,
            last_seen_at=now,
        )
        session.add(projection)
        return projection_id, "created"

    reactivated = projection.status != PROJECTION_ACTIVE
    changed = projection.sha256 != artifact.sha256 or reactivated
    projection.sha256 = artifact.sha256
    projection.contract = row.contract
    projection.contract_version = row.version
    projection.title = title
    projection.doi = doi
    projection.pmid = artifact.pmid
    projection.process_status = artifact.process_status
    projection.rights_status = artifact.rights_status
    projection.status = PROJECTION_ACTIVE
    projection.source_document_id = source_document_id
    projection.event_id = event_id
    projection.payload_json = payload
    projection.last_seen_at = now
    projection.revoked_at = None
    if reactivated:
        event.medical_review_status = MedicalReviewStatus.PENDING
    return projection_id, "updated" if changed else "unchanged"


def sync_collection(
    session: Session,
    knowledge_base_id: str,
    collection: WeKnoraCollection,
    *,
    now: datetime | None = None,
) -> SyncStats:
    """幂等写入待审投影，并把本次集合中消失的条目标记为 revoked。"""

    if not knowledge_base_id.strip():
        raise PullError("WeKnora KB ID 不能为空")
    now = (now or datetime.now(UTC)).astimezone(UTC).replace(tzinfo=None)
    seen: set[str] = set()
    created = updated = unchanged = revoked = 0
    for row in collection.data:
        artifact_id = row.artifact.artifact_id
        seen.add(artifact_id)
        _projection, outcome = _upsert_projection(session, knowledge_base_id, row, now)
        if outcome == "created":
            created += 1
        elif outcome == "updated":
            updated += 1
        else:
            unchanged += 1

    active_rows = session.scalars(
        select(WeKnoraEvidenceProjection).where(
            WeKnoraEvidenceProjection.knowledge_base_id == knowledge_base_id,
            WeKnoraEvidenceProjection.status == PROJECTION_ACTIVE,
        )
    ).all()
    for projection in active_rows:
        if projection.artifact_id in seen:
            continue
        projection.status = PROJECTION_REVOKED
        projection.revoked_at = now
        revoked += 1
    return SyncStats(created=created, updated=updated, unchanged=unchanged, revoked=revoked)


def is_active_weknora_event(session: Session, event_id: str) -> bool:
    """未绑定 WeKnora 投影的旧事件保持原行为；撤销投影不可继续发布。"""

    projection = session.scalar(
        select(WeKnoraEvidenceProjection).where(WeKnoraEvidenceProjection.event_id == event_id)
    )
    return projection is None or projection.status == PROJECTION_ACTIVE
