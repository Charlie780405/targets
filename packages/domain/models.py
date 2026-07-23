"""SQLAlchemy 2.0 领域模型 — 与 docs/event-schema.md 对齐。"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

from sqlalchemy import (
    JSON,
    Boolean,
    Date,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from packages.domain.database import Base
from packages.domain.enums import (
    EventType,
    EvidenceLevel,
    MedicalReviewStatus,
    Phase,
    ReportType,
    ResultDirection,
)


class Target(Base):
    __tablename__ = "targets"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    canonical_name: Mapped[str] = mapped_column(String(128), nullable=False)
    name_en: Mapped[str | None] = mapped_column(String(256))
    gene: Mapped[str | None] = mapped_column(String(32))
    pathway: Mapped[str | None] = mapped_column(String(256))
    notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )

    assets: Mapped[list[Asset]] = relationship(back_populates="target")


class Organization(Base):
    __tablename__ = "organizations"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    canonical_name: Mapped[str] = mapped_column(String(256), nullable=False)
    name_zh: Mapped[str | None] = mapped_column(String(128))
    country: Mapped[str | None] = mapped_column(String(8))
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )


class Indication(Base):
    __tablename__ = "indications"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    code: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    canonical_name: Mapped[str] = mapped_column(String(128), nullable=False)
    name_en: Mapped[str] = mapped_column(String(256), nullable=False)
    mesh_id: Mapped[str | None] = mapped_column(String(32))
    therapeutic_area: Mapped[str | None] = mapped_column(String(128))
    notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class Asset(Base):
    __tablename__ = "assets"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    inn: Mapped[str | None] = mapped_column(String(128))
    brand: Mapped[str | None] = mapped_column(String(128))
    target_id: Mapped[str] = mapped_column(ForeignKey("targets.id"), nullable=False)
    modality: Mapped[str | None] = mapped_column(String(128))
    mechanism: Mapped[str | None] = mapped_column(String(256))
    confidence: Mapped[str | None] = mapped_column(String(16))
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    target: Mapped[Target] = relationship(back_populates="assets")


class Trial(Base):
    """临床试验 — 001b 版本 diff 监测字段见 watch_* 列与 TrialSnapshot。"""

    __tablename__ = "trials"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    nct_id: Mapped[str | None] = mapped_column(String(32), unique=True)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    overall_status: Mapped[str | None] = mapped_column(String(64))
    phase: Mapped[Phase | None] = mapped_column(Enum(Phase, native_enum=False))
    enrollment: Mapped[int | None] = mapped_column(Integer)
    primary_completion_date: Mapped[date | None] = mapped_column(Date)
    study_completion_date: Mapped[date | None] = mapped_column(Date)
    outcome_measures: Mapped[str | None] = mapped_column(Text)
    results_posted: Mapped[bool] = mapped_column(Boolean, default=False)
    sponsor_org_id: Mapped[str | None] = mapped_column(ForeignKey("organizations.id"))
    target_id: Mapped[str | None] = mapped_column(ForeignKey("targets.id"))
    asset_id: Mapped[str | None] = mapped_column(ForeignKey("assets.id"))
    indication_id: Mapped[str | None] = mapped_column(ForeignKey("indications.id"))
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    raw_snapshot_path: Mapped[str | None] = mapped_column(String(512))
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )

    snapshots: Mapped[list[TrialSnapshot]] = relationship(back_populates="trial")


class TrialSnapshot(Base):
    """试验抓取快照 — 001b 字段 diff 比较用。"""

    __tablename__ = "trial_snapshots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    trial_id: Mapped[str] = mapped_column(ForeignKey("trials.id"), nullable=False)
    snapshot_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    payload_json: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    watch_fields_hash: Mapped[str | None] = mapped_column(String(64))

    trial: Mapped[Trial] = relationship(back_populates="snapshots")


class Publication(Base):
    __tablename__ = "publications"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    pmid: Mapped[str | None] = mapped_column(String(32), unique=True)
    doi: Mapped[str | None] = mapped_column(String(128), unique=True)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    abstract: Mapped[str | None] = mapped_column(Text)
    published_at: Mapped[date | None] = mapped_column(Date)
    retracted: Mapped[bool] = mapped_column(Boolean, default=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class Conference(Base):
    __tablename__ = "conferences"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(256), nullable=False)
    year: Mapped[int | None] = mapped_column(Integer)
    venue: Mapped[str | None] = mapped_column(String(256))
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class SourceDocument(Base):
    __tablename__ = "source_documents"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    source_id: Mapped[str] = mapped_column(String(64), nullable=False)
    source_name: Mapped[str] = mapped_column(String(128), nullable=False)
    source_url: Mapped[str] = mapped_column(String(1024), nullable=False)
    title: Mapped[str | None] = mapped_column(Text)
    published_at: Mapped[datetime | None] = mapped_column(DateTime)
    fetched_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    raw_path: Mapped[str | None] = mapped_column(String(512))
    payload_json: Mapped[dict[str, Any] | None] = mapped_column(JSON)

    __table_args__ = (UniqueConstraint("source_url", "content_hash", name="uq_source_doc_url_hash"),)


class Event(Base):
    __tablename__ = "events"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    event_type: Mapped[EventType] = mapped_column(Enum(EventType, native_enum=False), nullable=False)
    target_id: Mapped[str | None] = mapped_column(ForeignKey("targets.id"))
    asset_id: Mapped[str | None] = mapped_column(ForeignKey("assets.id"))
    indication_id: Mapped[str | None] = mapped_column(ForeignKey("indications.id"))
    organization_id: Mapped[str | None] = mapped_column(ForeignKey("organizations.id"))
    event_date: Mapped[date] = mapped_column(Date, nullable=False)
    discovered_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    title: Mapped[str] = mapped_column(Text, nullable=False)
    summary: Mapped[str | None] = mapped_column(Text)
    result_direction: Mapped[ResultDirection | None] = mapped_column(
        Enum(ResultDirection, native_enum=False)
    )
    phase: Mapped[Phase | None] = mapped_column(Enum(Phase, native_enum=False))
    significance_score: Mapped[float | None] = mapped_column(Float)
    confidence_score: Mapped[float | None] = mapped_column(Float)
    novelty_score: Mapped[float | None] = mapped_column(Float)
    medical_review_status: Mapped[MedicalReviewStatus] = mapped_column(
        Enum(MedicalReviewStatus, native_enum=False),
        default=MedicalReviewStatus.PENDING,
        nullable=False,
    )
    source_count: Mapped[int] = mapped_column(Integer, default=0)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    related_event_id: Mapped[str | None] = mapped_column(ForeignKey("events.id"))

    evidences: Mapped[list[Evidence]] = relationship(back_populates="event")


class Evidence(Base):
    __tablename__ = "evidences"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    event_id: Mapped[str] = mapped_column(ForeignKey("events.id"), nullable=False)
    source_document_id: Mapped[str | None] = mapped_column(ForeignKey("source_documents.id"))
    source_name: Mapped[str] = mapped_column(String(128), nullable=False)
    source_url: Mapped[str] = mapped_column(String(1024), nullable=False)
    evidence_snippet: Mapped[str | None] = mapped_column(Text)
    evidence_level: Mapped[EvidenceLevel] = mapped_column(
        Enum(EvidenceLevel, native_enum=False), nullable=False
    )
    published_at: Mapped[datetime | None] = mapped_column(DateTime)
    fetched_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)

    event: Mapped[Event] = relationship(back_populates="evidences")


class Report(Base):
    __tablename__ = "reports"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    report_type: Mapped[ReportType] = mapped_column(Enum(ReportType, native_enum=False), nullable=False)
    period_start: Mapped[date] = mapped_column(Date, nullable=False)
    period_end: Mapped[date] = mapped_column(Date, nullable=False)
    title: Mapped[str] = mapped_column(String(256), nullable=False)
    body_markdown: Mapped[str] = mapped_column(Text, nullable=False)
    target_id: Mapped[str | None] = mapped_column(ForeignKey("targets.id"))
    generated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
