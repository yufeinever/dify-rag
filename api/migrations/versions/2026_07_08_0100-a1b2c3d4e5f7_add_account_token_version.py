"""add account token version

Revision ID: a1b2c3d4e5f7
Revises: f1a2b3c4d5e6
Create Date: 2026-07-08 01:00:00.000000

"""

import sqlalchemy as sa
from alembic import op


revision = "a1b2c3d4e5f7"
down_revision = "f1a2b3c4d5e6"
branch_labels = None
depends_on = None


def _has_column(conn, table_name: str, column_name: str) -> bool:
    return any(column["name"] == column_name for column in sa.inspect(conn).get_columns(table_name))


def upgrade():
    conn = op.get_bind()
    if _has_column(conn, "accounts", "token_version"):
        return
    with op.batch_alter_table("accounts", schema=None) as batch_op:
        batch_op.add_column(sa.Column("token_version", sa.Integer(), server_default=sa.text("0"), nullable=False))


def downgrade():
    conn = op.get_bind()
    if not _has_column(conn, "accounts", "token_version"):
        return
    with op.batch_alter_table("accounts", schema=None) as batch_op:
        batch_op.drop_column("token_version")
