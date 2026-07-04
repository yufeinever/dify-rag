"""add_channel_integrations

Revision ID: e5f6a7b8c9d0
Revises: d4e8f6a1b2c3
Create Date: 2026-07-04 12:30:00.000000

"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

import models.types

revision = "e5f6a7b8c9d0"
down_revision = "d4e8f6a1b2c3"
branch_labels = None
depends_on = None


def _uuid_type(conn):
    return postgresql.UUID() if conn.dialect.name == "postgresql" else models.types.StringUUID()


def _long_text_type(conn):
    return sa.Text() if conn.dialect.name == "postgresql" else models.types.LongText()


def upgrade():
    conn = op.get_bind()
    uuid_type = _uuid_type(conn)
    long_text = _long_text_type(conn)
    timestamp_default = (
        sa.text("CURRENT_TIMESTAMP(0)") if conn.dialect.name == "postgresql" else sa.func.current_timestamp()
    )
    uuid_default = sa.text("uuid_generate_v4()") if conn.dialect.name == "postgresql" else None

    op.create_table(
        "channel_integration_bots",
        sa.Column("id", uuid_type, server_default=uuid_default, nullable=False),
        sa.Column("tenant_id", uuid_type, nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("channel", sa.String(length=32), nullable=False, server_default="feishu"),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("app_id", sa.String(length=255), nullable=False),
        sa.Column("encrypted_app_secret", long_text, nullable=False),
        sa.Column("encrypted_verification_token", long_text, nullable=False),
        sa.Column("encrypted_encrypt_key", long_text, nullable=False),
        sa.Column("bot_name", sa.String(length=255), nullable=True),
        sa.Column("bot_open_id", sa.String(length=255), nullable=True),
        sa.Column("callback_token", sa.String(length=64), nullable=False),
        sa.Column("last_verified_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=timestamp_default, nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=timestamp_default, nullable=False),
        sa.PrimaryKeyConstraint("id", name="channel_integration_bot_pkey"),
    )
    op.create_index("channel_integration_bot_tenant_idx", "channel_integration_bots", ["tenant_id"])
    op.create_index(
        "channel_integration_bot_tenant_name_idx",
        "channel_integration_bots",
        ["tenant_id", "name"],
        unique=True,
    )

    op.create_table(
        "channel_integration_app_bindings",
        sa.Column("id", uuid_type, server_default=uuid_default, nullable=False),
        sa.Column("tenant_id", uuid_type, nullable=False),
        sa.Column("bot_id", uuid_type, nullable=False),
        sa.Column("app_id", uuid_type, nullable=False),
        sa.Column("purpose", sa.String(length=32), nullable=False),
        sa.Column("priority", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(), server_default=timestamp_default, nullable=False),
        sa.ForeignKeyConstraint(["bot_id"], ["channel_integration_bots.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["app_id"], ["apps.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name="channel_integration_app_binding_pkey"),
    )
    op.create_index("channel_integration_app_binding_bot_idx", "channel_integration_app_bindings", ["bot_id"])
    op.create_index(
        "channel_integration_app_binding_bot_purpose_idx",
        "channel_integration_app_bindings",
        ["bot_id", "purpose"],
        unique=True,
    )


def downgrade():
    op.drop_index("channel_integration_app_binding_bot_purpose_idx", table_name="channel_integration_app_bindings")
    op.drop_index("channel_integration_app_binding_bot_idx", table_name="channel_integration_app_bindings")
    op.drop_table("channel_integration_app_bindings")
    op.drop_index("channel_integration_bot_tenant_name_idx", table_name="channel_integration_bots")
    op.drop_index("channel_integration_bot_tenant_idx", table_name="channel_integration_bots")
    op.drop_table("channel_integration_bots")
