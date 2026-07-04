from __future__ import annotations

import enum
from datetime import datetime
from uuid import uuid4

import sqlalchemy as sa
from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from .base import TypeBase
from .types import LongText, StringUUID


class ChannelIntegrationType(enum.StrEnum):
    FEISHU = "feishu"


class ChannelIntegrationBindingPurpose(enum.StrEnum):
    DEFAULT = "default"
    COPYWRITING = "copywriting"
    POSTER = "poster"


class ChannelIntegrationBot(TypeBase):
    __tablename__ = "channel_integration_bots"
    __table_args__ = (
        sa.PrimaryKeyConstraint("id", name="channel_integration_bot_pkey"),
        sa.Index("channel_integration_bot_tenant_idx", "tenant_id"),
        sa.Index("channel_integration_bot_tenant_name_idx", "tenant_id", "name", unique=True),
    )

    id: Mapped[str] = mapped_column(
        StringUUID, insert_default=lambda: str(uuid4()), default_factory=lambda: str(uuid4()), init=False
    )
    tenant_id: Mapped[str] = mapped_column(StringUUID, nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    app_id: Mapped[str] = mapped_column(String(255), nullable=False)
    encrypted_app_secret: Mapped[str] = mapped_column(LongText, nullable=False)
    encrypted_verification_token: Mapped[str] = mapped_column(LongText, nullable=False)
    encrypted_encrypt_key: Mapped[str] = mapped_column(LongText, nullable=False)
    callback_token: Mapped[str] = mapped_column(String(64), nullable=False)
    channel: Mapped[str] = mapped_column(String(32), nullable=False, default=ChannelIntegrationType.FEISHU.value)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    bot_name: Mapped[str | None] = mapped_column(String(255), nullable=True, default=None)
    bot_open_id: Mapped[str | None] = mapped_column(String(255), nullable=True, default=None)
    last_verified_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, default=None)
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


class ChannelIntegrationAppBinding(TypeBase):
    __tablename__ = "channel_integration_app_bindings"
    __table_args__ = (
        sa.PrimaryKeyConstraint("id", name="channel_integration_app_binding_pkey"),
        sa.Index("channel_integration_app_binding_bot_idx", "bot_id"),
        sa.Index("channel_integration_app_binding_bot_purpose_idx", "bot_id", "purpose", unique=True),
    )

    id: Mapped[str] = mapped_column(
        StringUUID, insert_default=lambda: str(uuid4()), default_factory=lambda: str(uuid4()), init=False
    )
    tenant_id: Mapped[str] = mapped_column(StringUUID, nullable=False)
    bot_id: Mapped[str] = mapped_column(
        StringUUID, ForeignKey("channel_integration_bots.id", ondelete="CASCADE"), nullable=False
    )
    app_id: Mapped[str] = mapped_column(StringUUID, ForeignKey("apps.id", ondelete="CASCADE"), nullable=False)
    purpose: Mapped[str] = mapped_column(String(32), nullable=False)
    priority: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.current_timestamp(), init=False
    )
