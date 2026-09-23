"""WeKnora 批准证据在 Targets 的待审投影

Revision ID: 9b8f2c1d7e4a
Revises: 62cca6f53ae0
Create Date: 2026-09-24 00:00:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "9b8f2c1d7e4a"
down_revision: Union[str, None] = "62cca6f53ae0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "weknora_evidence_projections",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("knowledge_base_id", sa.String(length=128), nullable=False),
        sa.Column("artifact_id", sa.String(length=64), nullable=False),
        sa.Column("sha256", sa.String(length=64), nullable=False),
        sa.Column("contract", sa.String(length=128), nullable=False),
        sa.Column("contract_version", sa.Integer(), nullable=False),
        sa.Column("title", sa.Text(), nullable=True),
        sa.Column("doi", sa.String(length=128), nullable=True),
        sa.Column("pmid", sa.String(length=32), nullable=True),
        sa.Column("process_status", sa.String(length=32), nullable=False),
        sa.Column("rights_status", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("source_document_id", sa.String(length=64), nullable=True),
        sa.Column("event_id", sa.String(length=32), nullable=True),
        sa.Column("payload_json", sa.JSON(), nullable=False),
        sa.Column("first_seen_at", sa.DateTime(), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.Column("revoked_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.ForeignKeyConstraint(["source_document_id"], ["source_documents.id"]),
        sa.ForeignKeyConstraint(["event_id"], ["events.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("knowledge_base_id", "artifact_id", name="uq_weknora_projection_kb_artifact"),
    )


def downgrade() -> None:
    op.drop_table("weknora_evidence_projections")
