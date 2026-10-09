"""Initial quote builder schema.

Revision ID: 20260810_0001
Revises:
Create Date: 2026-08-10
"""
from alembic import op
import sqlalchemy as sa


revision = "20260810_0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("username", sa.String(80), nullable=False),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("display_name", sa.String(120), nullable=False),
        sa.Column("chinese_name", sa.String(120), nullable=True),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("phone", sa.String(40), nullable=False),
        sa.Column("license_number", sa.String(80), nullable=True),
        sa.Column("office_address", sa.String(255), nullable=True),
        sa.Column("qr_code_path", sa.String(500), nullable=True),
        sa.Column("role", sa.String(40), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("username"),
    )
    op.create_index("ix_users_username", "users", ["username"])
    op.create_table(
        "quote_sequences",
        sa.Column("date_key", sa.String(8), primary_key=True),
        sa.Column("next_value", sa.Integer(), nullable=False),
    )
    op.create_table(
        "quotes",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("quote_number", sa.String(32), nullable=False),
        sa.Column("customer_name", sa.String(200), nullable=False),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column("owner_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("current_draft_json", sa.JSON(), nullable=False),
        sa.Column("latest_version_number", sa.Integer(), nullable=False),
        sa.Column("copied_from_quote_id", sa.Integer(), sa.ForeignKey("quotes.id"), nullable=True),
        sa.Column("quote_date", sa.Date(), nullable=False),
        sa.Column("expiration_date", sa.Date(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("archived_at", sa.DateTime(), nullable=True),
        sa.UniqueConstraint("quote_number"),
    )
    op.create_index("ix_quotes_quote_number", "quotes", ["quote_number"])
    op.create_index("ix_quotes_status", "quotes", ["status"])
    op.create_index("ix_quotes_owner_user_id", "quotes", ["owner_user_id"])
    op.create_table(
        "quote_versions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("quote_id", sa.Integer(), sa.ForeignKey("quotes.id"), nullable=False),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column("locale", sa.String(10), nullable=False),
        sa.Column("quote_snapshot_json", sa.JSON(), nullable=False),
        sa.Column("render_payload_json", sa.JSON(), nullable=False),
        sa.Column("template_mobile_version", sa.String(30), nullable=False),
        sa.Column("template_pdf_version", sa.String(30), nullable=False),
        sa.Column("version_status", sa.String(30), nullable=False),
        sa.Column("warning_acknowledgements_json", sa.JSON(), nullable=False),
        sa.Column("change_note", sa.String(500), nullable=True),
        sa.Column("created_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("quote_id", "version_number", name="uq_quote_version_number"),
    )
    op.create_index("ix_quote_versions_quote_id", "quote_versions", ["quote_id"])
    op.create_table(
        "generated_files",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("quote_version_id", sa.Integer(), sa.ForeignKey("quote_versions.id"), nullable=False),
        sa.Column("file_type", sa.String(30), nullable=False),
        sa.Column("file_name", sa.String(255), nullable=False),
        sa.Column("file_path", sa.String(1000), nullable=False),
        sa.Column("content_hash", sa.String(64), nullable=True),
        sa.Column("file_size_bytes", sa.Integer(), nullable=True),
        sa.Column("generated_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("generated_at", sa.DateTime(), nullable=False),
        sa.Column("generation_status", sa.String(30), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
    )
    op.create_index("ix_generated_files_quote_version_id", "generated_files", ["quote_version_id"])
    op.create_table(
        "audit_logs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("actor_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("quote_id", sa.Integer(), sa.ForeignKey("quotes.id"), nullable=True),
        sa.Column("quote_version_id", sa.Integer(), sa.ForeignKey("quote_versions.id"), nullable=True),
        sa.Column("action", sa.String(50), nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_audit_logs_actor_user_id", "audit_logs", ["actor_user_id"])
    op.create_index("ix_audit_logs_quote_id", "audit_logs", ["quote_id"])
    op.create_index("ix_audit_logs_action", "audit_logs", ["action"])


def downgrade() -> None:
    op.drop_table("audit_logs")
    op.drop_table("generated_files")
    op.drop_table("quote_versions")
    op.drop_table("quotes")
    op.drop_table("quote_sequences")
    op.drop_table("users")

