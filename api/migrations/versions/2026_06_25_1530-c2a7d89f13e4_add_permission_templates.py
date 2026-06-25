"""add permission templates

Revision ID: c2a7d89f13e4
Revises: bf1e8d5d7c31
Create Date: 2026-06-25 15:30:00.000000

"""

import sqlalchemy as sa
from alembic import op

import models.types


revision = 'c2a7d89f13e4'
down_revision = 'bf1e8d5d7c31'
branch_labels = None
depends_on = None


def _is_pg(conn):
    return conn.dialect.name == 'postgresql'


def _has_table(conn, table_name):
    return sa.inspect(conn).has_table(table_name)


def _timestamp_default(conn):
    return sa.text('CURRENT_TIMESTAMP(0)') if _is_pg(conn) else sa.func.current_timestamp()


def upgrade():
    conn = op.get_bind()
    timestamp_default = _timestamp_default(conn)
    uuid_default = sa.text('uuid_generate_v4()') if _is_pg(conn) else None

    if not _has_table(conn, 'enterprise_permission_templates'):
        op.create_table(
            'enterprise_permission_templates',
            sa.Column('id', models.types.StringUUID(), server_default=uuid_default, nullable=False),
            sa.Column('tenant_id', models.types.StringUUID(), nullable=False),
            sa.Column('name', sa.String(length=120), nullable=False),
            sa.Column('description', sa.Text(), nullable=True),
            sa.Column('created_by', models.types.StringUUID(), nullable=False),
            sa.Column('created_at', sa.DateTime(), server_default=timestamp_default, nullable=False),
            sa.Column('updated_at', sa.DateTime(), server_default=timestamp_default, nullable=False),
            sa.PrimaryKeyConstraint('id', name='enterprise_permission_template_pkey'),
            sa.UniqueConstraint('tenant_id', 'name', name='unique_enterprise_permission_template_name'),
        )
        op.create_index('idx_enterprise_permission_templates_tenant_id', 'enterprise_permission_templates', ['tenant_id'], unique=False)

    if not _has_table(conn, 'enterprise_permission_template_members'):
        op.create_table(
            'enterprise_permission_template_members',
            sa.Column('id', models.types.StringUUID(), server_default=uuid_default, nullable=False),
            sa.Column('tenant_id', models.types.StringUUID(), nullable=False),
            sa.Column('template_id', models.types.StringUUID(), nullable=False),
            sa.Column('account_id', models.types.StringUUID(), nullable=False),
            sa.Column('created_at', sa.DateTime(), server_default=timestamp_default, nullable=False),
            sa.PrimaryKeyConstraint('id', name='enterprise_permission_template_member_pkey'),
            sa.UniqueConstraint('template_id', 'account_id', name='unique_enterprise_permission_template_member'),
        )
        op.create_index('idx_enterprise_permission_template_members_tenant_id', 'enterprise_permission_template_members', ['tenant_id'], unique=False)
        op.create_index('idx_enterprise_permission_template_members_template_id', 'enterprise_permission_template_members', ['template_id'], unique=False)

    if not _has_table(conn, 'enterprise_permission_template_apps'):
        op.create_table(
            'enterprise_permission_template_apps',
            sa.Column('id', models.types.StringUUID(), server_default=uuid_default, nullable=False),
            sa.Column('tenant_id', models.types.StringUUID(), nullable=False),
            sa.Column('template_id', models.types.StringUUID(), nullable=False),
            sa.Column('app_id', models.types.StringUUID(), nullable=False),
            sa.Column('created_at', sa.DateTime(), server_default=timestamp_default, nullable=False),
            sa.PrimaryKeyConstraint('id', name='enterprise_permission_template_app_pkey'),
            sa.UniqueConstraint('template_id', 'app_id', name='unique_enterprise_permission_template_app'),
        )
        op.create_index('idx_enterprise_permission_template_apps_tenant_id', 'enterprise_permission_template_apps', ['tenant_id'], unique=False)
        op.create_index('idx_enterprise_permission_template_apps_template_id', 'enterprise_permission_template_apps', ['template_id'], unique=False)

    if not _has_table(conn, 'enterprise_permission_template_datasets'):
        op.create_table(
            'enterprise_permission_template_datasets',
            sa.Column('id', models.types.StringUUID(), server_default=uuid_default, nullable=False),
            sa.Column('tenant_id', models.types.StringUUID(), nullable=False),
            sa.Column('template_id', models.types.StringUUID(), nullable=False),
            sa.Column('dataset_id', models.types.StringUUID(), nullable=False),
            sa.Column('created_at', sa.DateTime(), server_default=timestamp_default, nullable=False),
            sa.PrimaryKeyConstraint('id', name='enterprise_permission_template_dataset_pkey'),
            sa.UniqueConstraint('template_id', 'dataset_id', name='unique_enterprise_permission_template_dataset'),
        )
        op.create_index('idx_enterprise_permission_template_datasets_tenant_id', 'enterprise_permission_template_datasets', ['tenant_id'], unique=False)
        op.create_index('idx_enterprise_permission_template_datasets_template_id', 'enterprise_permission_template_datasets', ['template_id'], unique=False)


def downgrade():
    conn = op.get_bind()
    tables = (
        ('enterprise_permission_template_datasets', ('idx_enterprise_permission_template_datasets_template_id', 'idx_enterprise_permission_template_datasets_tenant_id')),
        ('enterprise_permission_template_apps', ('idx_enterprise_permission_template_apps_template_id', 'idx_enterprise_permission_template_apps_tenant_id')),
        ('enterprise_permission_template_members', ('idx_enterprise_permission_template_members_template_id', 'idx_enterprise_permission_template_members_tenant_id')),
        ('enterprise_permission_templates', ('idx_enterprise_permission_templates_tenant_id',)),
    )
    inspector = sa.inspect(conn)
    for table_name, index_names in tables:
        if not inspector.has_table(table_name):
            continue
        existing_indexes = {index['name'] for index in inspector.get_indexes(table_name)}
        for index_name in index_names:
            if index_name in existing_indexes:
                op.drop_index(index_name, table_name=table_name)
        op.drop_table(table_name)
