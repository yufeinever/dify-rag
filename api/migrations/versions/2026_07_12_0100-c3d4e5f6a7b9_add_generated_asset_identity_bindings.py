"""add generated asset identity bindings

Revision ID: c3d4e5f6a7b9
Revises: b2c3d4e5f6a8
Create Date: 2026-07-12 01:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "c3d4e5f6a7b9"
down_revision: str | None = "b2c3d4e5f6a8"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "generated_asset_identity_bindings",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("end_user_id", sa.Uuid(), nullable=False),
        sa.Column("account_id", sa.Uuid(), nullable=True),
        sa.Column("channel_type", sa.String(length=64), nullable=False, server_default="unknown"),
        sa.Column("display_name", sa.String(length=255), nullable=True),
        sa.Column("is_test", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("created_by", sa.Uuid(), nullable=False),
        sa.Column("updated_by", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.current_timestamp()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.current_timestamp()),
        sa.PrimaryKeyConstraint("id", name="generated_asset_identity_binding_pkey"),
        sa.UniqueConstraint("tenant_id", "end_user_id", name="generated_asset_identity_binding_tenant_end_user_unique"),
    )
    op.create_index(
        "generated_asset_identity_binding_account_idx",
        "generated_asset_identity_bindings",
        ["tenant_id", "account_id"],
    )
    op.create_index(
        "generated_asset_identity_binding_channel_idx",
        "generated_asset_identity_bindings",
        ["tenant_id", "channel_type"],
    )


def downgrade() -> None:
    op.drop_index("generated_asset_identity_binding_channel_idx", table_name="generated_asset_identity_bindings")
    op.drop_index("generated_asset_identity_binding_account_idx", table_name="generated_asset_identity_bindings")
    op.drop_table("generated_asset_identity_bindings")
