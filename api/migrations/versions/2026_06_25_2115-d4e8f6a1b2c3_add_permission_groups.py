"""add permission groups

Revision ID: d4e8f6a1b2c3
Revises: a9b4c2d7e6f1
Create Date: 2026-06-25 21:15:00.000000

"""

import sqlalchemy as sa
from alembic import op

import models.types

revision = "d4e8f6a1b2c3"
down_revision = "a9b4c2d7e6f1"
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
    timestamp_default = _timestamp_default(conn)
    uuid_default = sa.text("uuid_generate_v4()") if _is_pg(conn) else None

    if not _has_table(conn, "enterprise_permission_groups"):
        op.create_table(
            "enterprise_permission_groups",
            sa.Column("id", models.types.StringUUID(), server_default=uuid_default, nullable=False),
            sa.Column("tenant_id", models.types.StringUUID(), nullable=False),
            sa.Column("name", sa.String(length=120), nullable=False),
            sa.Column("description", sa.Text(), nullable=True),
            sa.Column("created_by", models.types.StringUUID(), nullable=False),
            sa.Column("created_at", sa.DateTime(), server_default=timestamp_default, nullable=False),
            sa.Column("updated_at", sa.DateTime(), server_default=timestamp_default, nullable=False),
            sa.PrimaryKeyConstraint("id", name="enterprise_permission_group_pkey"),
            sa.UniqueConstraint("tenant_id", "name", name="unique_enterprise_permission_group_name"),
        )
        op.create_index(
            "idx_enterprise_permission_groups_tenant_id",
            "enterprise_permission_groups",
            ["tenant_id"],
            unique=False,
        )

    if not _has_table(conn, "enterprise_permission_group_members"):
        op.create_table(
            "enterprise_permission_group_members",
            sa.Column("id", models.types.StringUUID(), server_default=uuid_default, nullable=False),
            sa.Column("tenant_id", models.types.StringUUID(), nullable=False),
            sa.Column("group_id", models.types.StringUUID(), nullable=False),
            sa.Column("account_id", models.types.StringUUID(), nullable=False),
            sa.Column("created_at", sa.DateTime(), server_default=timestamp_default, nullable=False),
            sa.PrimaryKeyConstraint("id", name="enterprise_permission_group_member_pkey"),
            sa.UniqueConstraint("group_id", "account_id", name="unique_enterprise_permission_group_member"),
        )
        op.create_index(
            "idx_enterprise_permission_group_members_tenant_id",
            "enterprise_permission_group_members",
            ["tenant_id"],
            unique=False,
        )
        op.create_index(
            "idx_enterprise_permission_group_members_group_id",
            "enterprise_permission_group_members",
            ["group_id"],
            unique=False,
        )

    if not _has_table(conn, "enterprise_permission_template_groups"):
        op.create_table(
            "enterprise_permission_template_groups",
            sa.Column("id", models.types.StringUUID(), server_default=uuid_default, nullable=False),
            sa.Column("tenant_id", models.types.StringUUID(), nullable=False),
            sa.Column("template_id", models.types.StringUUID(), nullable=False),
            sa.Column("group_id", models.types.StringUUID(), nullable=False),
            sa.Column("created_at", sa.DateTime(), server_default=timestamp_default, nullable=False),
            sa.PrimaryKeyConstraint("id", name="enterprise_permission_template_group_pkey"),
            sa.UniqueConstraint("template_id", "group_id", name="unique_enterprise_permission_template_group"),
        )
        op.create_index(
            "idx_enterprise_permission_template_groups_tenant_id",
            "enterprise_permission_template_groups",
            ["tenant_id"],
            unique=False,
        )
        op.create_index(
            "idx_enterprise_permission_template_groups_template_id",
            "enterprise_permission_template_groups",
            ["template_id"],
            unique=False,
        )


def downgrade():
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    tables = (
        (
            "enterprise_permission_template_groups",
            (
                "idx_enterprise_permission_template_groups_template_id",
                "idx_enterprise_permission_template_groups_tenant_id",
            ),
        ),
        (
            "enterprise_permission_group_members",
            ("idx_enterprise_permission_group_members_group_id", "idx_enterprise_permission_group_members_tenant_id"),
        ),
        ("enterprise_permission_groups", ("idx_enterprise_permission_groups_tenant_id",)),
    )
    for table_name, index_names in tables:
        if not inspector.has_table(table_name):
            continue
        existing_indexes = {index["name"] for index in inspector.get_indexes(table_name)}
        for index_name in index_names:
            if index_name in existing_indexes:
                op.drop_index(index_name, table_name=table_name)
        op.drop_table(table_name)
