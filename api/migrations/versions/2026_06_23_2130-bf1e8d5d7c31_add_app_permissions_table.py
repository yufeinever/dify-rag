"""add app permissions table

Revision ID: bf1e8d5d7c31
Revises: f8b6b7e9c421
Create Date: 2026-06-23 21:30:00.000000

"""

import sqlalchemy as sa
from alembic import op

import models.types


def _is_pg(conn):
    return conn.dialect.name == 'postgresql'


def _has_table(conn, table_name):
    return sa.inspect(conn).has_table(table_name)


def _has_index(conn, table_name, index_name):
    inspector = sa.inspect(conn)
    return any(index['name'] == index_name for index in inspector.get_indexes(table_name))


revision = 'bf1e8d5d7c31'
down_revision = 'f8b6b7e9c421'
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()

    if not _has_table(conn, 'app_permissions'):
        if _is_pg(conn):
            op.create_table(
                'app_permissions',
                sa.Column('id', models.types.StringUUID(), server_default=sa.text('uuid_generate_v4()'), nullable=False),
                sa.Column('app_id', models.types.StringUUID(), nullable=False),
                sa.Column('account_id', models.types.StringUUID(), nullable=False),
                sa.Column('tenant_id', models.types.StringUUID(), nullable=False),
                sa.Column('has_permission', sa.Boolean(), server_default=sa.text('true'), nullable=False),
                sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP(0)'), nullable=False),
                sa.PrimaryKeyConstraint('id', name='app_permission_pkey'),
            )
        else:
            op.create_table(
                'app_permissions',
                sa.Column('id', models.types.StringUUID(), nullable=False),
                sa.Column('app_id', models.types.StringUUID(), nullable=False),
                sa.Column('account_id', models.types.StringUUID(), nullable=False),
                sa.Column('tenant_id', models.types.StringUUID(), nullable=False),
                sa.Column('has_permission', sa.Boolean(), server_default=sa.text('true'), nullable=False),
                sa.Column('created_at', sa.DateTime(), server_default=sa.func.current_timestamp(), nullable=False),
                sa.PrimaryKeyConstraint('id', name='app_permission_pkey'),
            )

    indexes = (
        ('idx_app_permissions_app_id', ['app_id']),
        ('idx_app_permissions_account_id', ['account_id']),
        ('idx_app_permissions_tenant_id', ['tenant_id']),
    )
    for index_name, columns in indexes:
        if not _has_index(conn, 'app_permissions', index_name):
            op.create_index(index_name, 'app_permissions', columns, unique=False)


def downgrade():
    conn = op.get_bind()

    if not _has_table(conn, 'app_permissions'):
        return

    indexes = (
        'idx_app_permissions_tenant_id',
        'idx_app_permissions_account_id',
        'idx_app_permissions_app_id',
    )
    for index_name in indexes:
        if _has_index(conn, 'app_permissions', index_name):
            op.drop_index(index_name, table_name='app_permissions')

    op.drop_table('app_permissions')
