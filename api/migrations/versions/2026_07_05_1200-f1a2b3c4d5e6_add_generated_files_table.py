"""add generated files library

Revision ID: f1a2b3c4d5e6
Revises: e5f6a7b8c9d0
Create Date: 2026-07-05 12:00:00.000000

"""

import sqlalchemy as sa
from alembic import op

import models.types

revision = "f1a2b3c4d5e6"
down_revision = "e5f6a7b8c9d0"
branch_labels = None
depends_on = None


def _is_pg(conn):
    return conn.dialect.name == "postgresql"


def _has_table(conn, table_name):
    return sa.inspect(conn).has_table(table_name)


def _timestamp_default(conn):
    return sa.text("CURRENT_TIMESTAMP(0)") if _is_pg(conn) else sa.func.current_timestamp()


def upgrade():
    conn = op.get_bind()
    if _has_table(conn, "generated_files"):
        return

    op.create_table(
        "generated_files",
        sa.Column(
            "id",
            models.types.StringUUID(),
            server_default=sa.text("uuid_generate_v4()") if _is_pg(conn) else None,
            nullable=False,
        ),
        sa.Column("tenant_id", models.types.StringUUID(), nullable=False),
        sa.Column("owner_user_id", models.types.StringUUID(), nullable=False),
        sa.Column("tool_file_id", models.types.StringUUID(), nullable=False),
        sa.Column("source_app_id", models.types.StringUUID(), nullable=True),
        sa.Column("source_conversation_id", models.types.StringUUID(), nullable=True),
        sa.Column("source_message_id", models.types.StringUUID(), nullable=True),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("mime_type", sa.String(length=255), nullable=False),
        sa.Column("file_type", sa.String(length=64), nullable=False),
        sa.Column("size", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=_timestamp_default(conn), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=_timestamp_default(conn), nullable=False),
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id", name="generated_file_pkey"),
        sa.UniqueConstraint("tool_file_id", name="generated_file_tool_file_unique"),
    )
    op.create_index(
        "generated_file_tenant_owner_created_at_idx",
        "generated_files",
        ["tenant_id", "owner_user_id", "created_at"],
    )
    op.create_index(
        "generated_file_tenant_file_type_created_at_idx",
        "generated_files",
        ["tenant_id", "file_type", "created_at"],
    )
    op.create_index("generated_file_source_app_idx", "generated_files", ["source_app_id"])


def downgrade():
    conn = op.get_bind()
    if not _has_table(conn, "generated_files"):
        return
    op.drop_index("generated_file_source_app_idx", table_name="generated_files")
    op.drop_index("generated_file_tenant_file_type_created_at_idx", table_name="generated_files")
    op.drop_index("generated_file_tenant_owner_created_at_idx", table_name="generated_files")
    op.drop_table("generated_files")
