"""expand generated files to generated assets

Revision ID: b2c3d4e5f6a8
Revises: a1b2c3d4e5f7
Create Date: 2026-07-11 01:00:00.000000

"""

import sqlalchemy as sa
from alembic import op

import models.types

revision = "b2c3d4e5f6a8"
down_revision = "a1b2c3d4e5f7"
branch_labels = None
depends_on = None


def _column_names(conn, table_name: str) -> set[str]:
    return {column["name"] for column in sa.inspect(conn).get_columns(table_name)}


def _index_names(conn, table_name: str) -> set[str]:
    return {index["name"] for index in sa.inspect(conn).get_indexes(table_name) if index.get("name")}


def _unique_constraint_names(conn, table_name: str) -> set[str]:
    return {
        constraint["name"]
        for constraint in sa.inspect(conn).get_unique_constraints(table_name)
        if constraint.get("name")
    }


def upgrade():
    conn = op.get_bind()
    columns = _column_names(conn, "generated_files")
    additions = [
        ("storage_type", sa.Column("storage_type", sa.String(length=32), server_default="tool_file", nullable=False)),
        ("source_url", sa.Column("source_url", sa.Text(), nullable=True)),
        ("thumbnail_url", sa.Column("thumbnail_url", sa.Text(), nullable=True)),
        (
            "source_workflow_run_id",
            sa.Column("source_workflow_run_id", models.types.StringUUID(), nullable=True),
        ),
        ("source_kind", sa.Column("source_kind", sa.String(length=64), server_default="message_file", nullable=False)),
        ("source_key", sa.Column("source_key", sa.String(length=255), nullable=True)),
        ("asset_metadata", sa.Column("asset_metadata", sa.JSON(), server_default=sa.text("'{}'"), nullable=False)),
    ]
    with op.batch_alter_table("generated_files", schema=None) as batch_op:
        if not sa.inspect(conn).get_columns("generated_files"):
            return
        batch_op.alter_column(
            "tool_file_id",
            existing_type=models.types.StringUUID(),
            nullable=True,
        )
        for name, column in additions:
            if name not in columns:
                batch_op.add_column(column)

    indexes = _index_names(conn, "generated_files")
    if "generated_file_tenant_source_kind_created_at_idx" not in indexes:
        op.create_index(
            "generated_file_tenant_source_kind_created_at_idx",
            "generated_files",
            ["tenant_id", "source_kind", "created_at"],
        )
    if "generated_file_source_workflow_run_idx" not in indexes:
        op.create_index(
            "generated_file_source_workflow_run_idx",
            "generated_files",
            ["source_workflow_run_id"],
        )

    constraints = _unique_constraint_names(conn, "generated_files")
    if "generated_file_tenant_source_key_unique" not in constraints:
        with op.batch_alter_table("generated_files", schema=None) as batch_op:
            batch_op.create_unique_constraint(
                "generated_file_tenant_source_key_unique",
                ["tenant_id", "source_key"],
            )


def downgrade():
    conn = op.get_bind()
    null_tool_files = conn.scalar(sa.text("SELECT COUNT(*) FROM generated_files WHERE tool_file_id IS NULL"))
    if null_tool_files:
        raise RuntimeError("Cannot downgrade generated assets while remote asset rows exist.")

    indexes = _index_names(conn, "generated_files")
    if "generated_file_source_workflow_run_idx" in indexes:
        op.drop_index("generated_file_source_workflow_run_idx", table_name="generated_files")
    if "generated_file_tenant_source_kind_created_at_idx" in indexes:
        op.drop_index("generated_file_tenant_source_kind_created_at_idx", table_name="generated_files")

    constraints = _unique_constraint_names(conn, "generated_files")
    columns = _column_names(conn, "generated_files")
    with op.batch_alter_table("generated_files", schema=None) as batch_op:
        if "generated_file_tenant_source_key_unique" in constraints:
            batch_op.drop_constraint("generated_file_tenant_source_key_unique", type_="unique")
        for column_name in (
            "asset_metadata",
            "source_key",
            "source_kind",
            "source_workflow_run_id",
            "thumbnail_url",
            "source_url",
            "storage_type",
        ):
            if column_name in columns:
                batch_op.drop_column(column_name)
        batch_op.alter_column(
            "tool_file_id",
            existing_type=models.types.StringUUID(),
            nullable=False,
        )
