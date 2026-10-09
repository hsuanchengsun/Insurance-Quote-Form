"""Align lookup indexes with unique model columns.

Revision ID: 20260810_0002
Revises: 20260810_0001
Create Date: 2026-08-10
"""
from alembic import op


revision = "20260810_0002"
down_revision = "20260810_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_index("ix_quotes_quote_number", table_name="quotes")
    op.create_index("ix_quotes_quote_number", "quotes", ["quote_number"], unique=True)
    op.drop_index("ix_users_username", table_name="users")
    op.create_index("ix_users_username", "users", ["username"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_users_username", table_name="users")
    op.create_index("ix_users_username", "users", ["username"], unique=False)
    op.drop_index("ix_quotes_quote_number", table_name="quotes")
    op.create_index("ix_quotes_quote_number", "quotes", ["quote_number"], unique=False)

