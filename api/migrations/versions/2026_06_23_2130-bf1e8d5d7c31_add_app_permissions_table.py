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


revision = 'bf1e8d5d7c31'
down_revision = 'f8b6b7e9c421'
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()

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

    with op.batch_alter_table('app_permissions', schema=None) as batch_op:
        batch_op.create_index('idx_app_permissions_app_id', ['app_id'], unique=False)
        batch_op.create_index('idx_app_permissions_account_id', ['account_id'], unique=False)
        batch_op.create_index('idx_app_permissions_tenant_id', ['tenant_id'], unique=False)


def downgrade():
    with op.batch_alter_table('app_permissions', schema=None) as batch_op:
        batch_op.drop_index('idx_app_permissions_tenant_id')
        batch_op.drop_index('idx_app_permissions_account_id')
        batch_op.drop_index('idx_app_permissions_app_id')

    op.drop_table('app_permissions')
