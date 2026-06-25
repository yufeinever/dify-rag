"""add explore app permissions

Revision ID: a9b4c2d7e6f1
Revises: c2a7d89f13e4
Create Date: 2026-06-25 18:30:00.000000

"""

import sqlalchemy as sa
from alembic import op

import models.types

revision = 'a9b4c2d7e6f1'
down_revision = 'c2a7d89f13e4'
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

    if not _has_table(conn, 'explore_app_permissions'):
        op.create_table(
            'explore_app_permissions',
            sa.Column('id', models.types.StringUUID(), server_default=uuid_default, nullable=False),
            sa.Column('app_id', models.types.StringUUID(), nullable=False),
            sa.Column('account_id', models.types.StringUUID(), nullable=False),
            sa.Column('tenant_id', models.types.StringUUID(), nullable=False),
            sa.Column('has_permission', sa.Boolean(), server_default=sa.text('true'), nullable=False),
            sa.Column('created_at', sa.DateTime(), server_default=timestamp_default, nullable=False),
            sa.PrimaryKeyConstraint('id', name='explore_app_permission_pkey'),
        )
        op.create_index('idx_explore_app_permissions_app_id', 'explore_app_permissions', ['app_id'], unique=False)
        op.create_index(
            'idx_explore_app_permissions_account_id', 'explore_app_permissions', ['account_id'], unique=False
        )
        op.create_index('idx_explore_app_permissions_tenant_id', 'explore_app_permissions', ['tenant_id'], unique=False)

    if not _has_table(conn, 'enterprise_permission_template_explore_apps'):
        op.create_table(
            'enterprise_permission_template_explore_apps',
            sa.Column('id', models.types.StringUUID(), server_default=uuid_default, nullable=False),
            sa.Column('tenant_id', models.types.StringUUID(), nullable=False),
            sa.Column('template_id', models.types.StringUUID(), nullable=False),
            sa.Column('app_id', models.types.StringUUID(), nullable=False),
            sa.Column('created_at', sa.DateTime(), server_default=timestamp_default, nullable=False),
            sa.PrimaryKeyConstraint('id', name='enterprise_permission_template_explore_app_pkey'),
            sa.UniqueConstraint('template_id', 'app_id', name='unique_enterprise_permission_template_explore_app'),
        )
        op.create_index(
            'idx_enterprise_permission_template_explore_apps_tenant_id',
            'enterprise_permission_template_explore_apps',
            ['tenant_id'],
            unique=False,
        )
        op.create_index(
            'idx_enterprise_permission_template_explore_apps_template_id',
            'enterprise_permission_template_explore_apps',
            ['template_id'],
            unique=False,
        )


def downgrade():
    conn = op.get_bind()
    inspector = sa.inspect(conn)

    if inspector.has_table('enterprise_permission_template_explore_apps'):
        existing_indexes = {
            index['name'] for index in inspector.get_indexes('enterprise_permission_template_explore_apps')
        }
        for index_name in (
            'idx_enterprise_permission_template_explore_apps_template_id',
            'idx_enterprise_permission_template_explore_apps_tenant_id',
        ):
            if index_name in existing_indexes:
                op.drop_index(index_name, table_name='enterprise_permission_template_explore_apps')
        op.drop_table('enterprise_permission_template_explore_apps')

    if inspector.has_table('explore_app_permissions'):
        existing_indexes = {index['name'] for index in inspector.get_indexes('explore_app_permissions')}
        for index_name in (
            'idx_explore_app_permissions_tenant_id',
            'idx_explore_app_permissions_account_id',
            'idx_explore_app_permissions_app_id',
        ):
            if index_name in existing_indexes:
                op.drop_index(index_name, table_name='explore_app_permissions')
        op.drop_table('explore_app_permissions')
