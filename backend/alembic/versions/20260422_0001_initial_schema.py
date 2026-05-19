"""initial schema

Revision ID: 0001_initial_schema
Revises:
Create Date: 2026-04-22 00:00:00.000000
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "0001_initial_schema"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    job_status = postgresql.ENUM(
        "pending",
        "running",
        "completed",
        "failed",
        "cancelled",
        name="job_status",
    )
    page_status = postgresql.ENUM(
        "discovered",
        "queued",
        "fetched",
        "extracted",
        "failed",
        "skipped",
        name="page_status",
    )
    job_status.create(op.get_bind(), checkfirst=True)
    page_status.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "jobs",
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("status", job_status, nullable=False),
        sa.Column("seed_urls", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("extraction_schema", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("crawl_config", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("priority", sa.Integer(), nullable=False),
        sa.Column("max_pages", sa.Integer(), nullable=False),
        sa.Column("pages_discovered", sa.Integer(), nullable=False),
        sa.Column("pages_processed", sa.Integer(), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_jobs")),
    )
    op.create_index(op.f("ix_jobs_status"), "jobs", ["status"], unique=False)

    op.create_table(
        "pages",
        sa.Column("job_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("url", sa.Text(), nullable=False),
        sa.Column("canonical_url", sa.Text(), nullable=True),
        sa.Column("domain", sa.String(length=255), nullable=False),
        sa.Column("status", page_status, nullable=False),
        sa.Column("http_status", sa.Integer(), nullable=True),
        sa.Column("content_type", sa.String(length=255), nullable=True),
        sa.Column("title", sa.Text(), nullable=True),
        sa.Column("raw_html_sha256", sa.String(length=64), nullable=True),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("fetched_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.ForeignKeyConstraint(["job_id"], ["jobs.id"], name=op.f("fk_pages_job_id_jobs"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_pages")),
        sa.UniqueConstraint("job_id", "url", name="uq_pages_job_id_url"),
    )
    op.create_index(op.f("ix_pages_domain"), "pages", ["domain"], unique=False)
    op.create_index(op.f("ix_pages_job_id"), "pages", ["job_id"], unique=False)
    op.create_index(op.f("ix_pages_raw_html_sha256"), "pages", ["raw_html_sha256"], unique=False)
    op.create_index(op.f("ix_pages_status"), "pages", ["status"], unique=False)

    op.create_table(
        "extracted_data",
        sa.Column("page_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("extractor_name", sa.String(length=120), nullable=False),
        sa.Column("schema_name", sa.String(length=255), nullable=False),
        sa.Column("data", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("confidence", sa.Numeric(precision=5, scale=4), nullable=False),
        sa.Column("source_text", sa.Text(), nullable=True),
        sa.Column("validation_errors", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.ForeignKeyConstraint(["page_id"], ["pages.id"], name=op.f("fk_extracted_data_page_id_pages"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_extracted_data")),
    )
    op.create_index(op.f("ix_extracted_data_extractor_name"), "extracted_data", ["extractor_name"], unique=False)
    op.create_index(op.f("ix_extracted_data_page_id"), "extracted_data", ["page_id"], unique=False)
    op.create_index(op.f("ix_extracted_data_schema_name"), "extracted_data", ["schema_name"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_extracted_data_schema_name"), table_name="extracted_data")
    op.drop_index(op.f("ix_extracted_data_page_id"), table_name="extracted_data")
    op.drop_index(op.f("ix_extracted_data_extractor_name"), table_name="extracted_data")
    op.drop_table("extracted_data")

    op.drop_index(op.f("ix_pages_status"), table_name="pages")
    op.drop_index(op.f("ix_pages_raw_html_sha256"), table_name="pages")
    op.drop_index(op.f("ix_pages_job_id"), table_name="pages")
    op.drop_index(op.f("ix_pages_domain"), table_name="pages")
    op.drop_table("pages")

    op.drop_index(op.f("ix_jobs_status"), table_name="jobs")
    op.drop_table("jobs")

    postgresql.ENUM(name="page_status").drop(op.get_bind(), checkfirst=True)
    postgresql.ENUM(name="job_status").drop(op.get_bind(), checkfirst=True)
