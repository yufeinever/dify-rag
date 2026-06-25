from datetime import datetime
from uuid import uuid4

import sqlalchemy as sa
from sqlalchemy import DateTime, String, func
from sqlalchemy.orm import Mapped, mapped_column

from .base import TypeBase
from .types import StringUUID


class EnterprisePermissionTemplate(TypeBase):
    """Workspace-level reusable grants for members, explore apps, studio apps, and datasets."""

    __tablename__ = "enterprise_permission_templates"
    __table_args__ = (
        sa.PrimaryKeyConstraint("id", name="enterprise_permission_template_pkey"),
        sa.Index("idx_enterprise_permission_templates_tenant_id", "tenant_id"),
        sa.UniqueConstraint("tenant_id", "name", name="unique_enterprise_permission_template_name"),
    )

    id: Mapped[str] = mapped_column(
        StringUUID,
        insert_default=lambda: str(uuid4()),
        default_factory=lambda: str(uuid4()),
        primary_key=True,
        init=False,
    )
    tenant_id: Mapped[str] = mapped_column(StringUUID, nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    created_by: Mapped[str] = mapped_column(StringUUID, nullable=False)
    description: Mapped[str | None] = mapped_column(sa.Text, nullable=True, default=None)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.current_timestamp(), init=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=func.current_timestamp(),
        onupdate=func.current_timestamp(),
        init=False,
    )


class EnterprisePermissionTemplateMember(TypeBase):
    __tablename__ = "enterprise_permission_template_members"
    __table_args__ = (
        sa.PrimaryKeyConstraint("id", name="enterprise_permission_template_member_pkey"),
        sa.Index("idx_enterprise_permission_template_members_tenant_id", "tenant_id"),
        sa.Index("idx_enterprise_permission_template_members_template_id", "template_id"),
        sa.UniqueConstraint("template_id", "account_id", name="unique_enterprise_permission_template_member"),
    )

    id: Mapped[str] = mapped_column(
        StringUUID,
        insert_default=lambda: str(uuid4()),
        default_factory=lambda: str(uuid4()),
        primary_key=True,
        init=False,
    )
    tenant_id: Mapped[str] = mapped_column(StringUUID, nullable=False)
    template_id: Mapped[str] = mapped_column(StringUUID, nullable=False)
    account_id: Mapped[str] = mapped_column(StringUUID, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.current_timestamp(), init=False
    )


class EnterprisePermissionTemplateApp(TypeBase):
    __tablename__ = "enterprise_permission_template_apps"
    __table_args__ = (
        sa.PrimaryKeyConstraint("id", name="enterprise_permission_template_app_pkey"),
        sa.Index("idx_enterprise_permission_template_apps_tenant_id", "tenant_id"),
        sa.Index("idx_enterprise_permission_template_apps_template_id", "template_id"),
        sa.UniqueConstraint("template_id", "app_id", name="unique_enterprise_permission_template_app"),
    )

    id: Mapped[str] = mapped_column(
        StringUUID,
        insert_default=lambda: str(uuid4()),
        default_factory=lambda: str(uuid4()),
        primary_key=True,
        init=False,
    )
    tenant_id: Mapped[str] = mapped_column(StringUUID, nullable=False)
    template_id: Mapped[str] = mapped_column(StringUUID, nullable=False)
    app_id: Mapped[str] = mapped_column(StringUUID, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.current_timestamp(), init=False
    )


class EnterprisePermissionTemplateExploreApp(TypeBase):
    __tablename__ = "enterprise_permission_template_explore_apps"
    __table_args__ = (
        sa.PrimaryKeyConstraint("id", name="enterprise_permission_template_explore_app_pkey"),
        sa.Index("idx_enterprise_permission_template_explore_apps_tenant_id", "tenant_id"),
        sa.Index("idx_enterprise_permission_template_explore_apps_template_id", "template_id"),
        sa.UniqueConstraint(
            "template_id", "app_id", name="unique_enterprise_permission_template_explore_app"
        ),
    )

    id: Mapped[str] = mapped_column(
        StringUUID,
        insert_default=lambda: str(uuid4()),
        default_factory=lambda: str(uuid4()),
        primary_key=True,
        init=False,
    )
    tenant_id: Mapped[str] = mapped_column(StringUUID, nullable=False)
    template_id: Mapped[str] = mapped_column(StringUUID, nullable=False)
    app_id: Mapped[str] = mapped_column(StringUUID, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.current_timestamp(), init=False
    )


class EnterprisePermissionTemplateDataset(TypeBase):
    __tablename__ = "enterprise_permission_template_datasets"
    __table_args__ = (
        sa.PrimaryKeyConstraint("id", name="enterprise_permission_template_dataset_pkey"),
        sa.Index("idx_enterprise_permission_template_datasets_tenant_id", "tenant_id"),
        sa.Index("idx_enterprise_permission_template_datasets_template_id", "template_id"),
        sa.UniqueConstraint("template_id", "dataset_id", name="unique_enterprise_permission_template_dataset"),
    )

    id: Mapped[str] = mapped_column(
        StringUUID,
        insert_default=lambda: str(uuid4()),
        default_factory=lambda: str(uuid4()),
        primary_key=True,
        init=False,
    )
    tenant_id: Mapped[str] = mapped_column(StringUUID, nullable=False)
    template_id: Mapped[str] = mapped_column(StringUUID, nullable=False)
    dataset_id: Mapped[str] = mapped_column(StringUUID, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.current_timestamp(), init=False
    )
