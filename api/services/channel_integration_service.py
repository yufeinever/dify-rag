from __future__ import annotations

import secrets
from datetime import datetime
from typing import Any

from sqlalchemy import delete, select

from constants import HIDDEN_VALUE
from core.helper.encrypter import decrypt_token, encrypt_token
from extensions.ext_database import db
from models.channel_integration import (
    ChannelIntegrationAppBinding,
    ChannelIntegrationBindingPurpose,
    ChannelIntegrationBot,
    ChannelIntegrationType,
)
from models.enums import ApiTokenType
from models.model import ApiToken, App

SECRET_FIELDS = ("app_secret", "verification_token", "encrypt_key")


class ChannelIntegrationService:
    @staticmethod
    def list_bots(tenant_id: str) -> list[ChannelIntegrationBot]:
        return list(
            db.session.scalars(
                select(ChannelIntegrationBot)
                .where(ChannelIntegrationBot.tenant_id == tenant_id)
                .order_by(ChannelIntegrationBot.created_at.desc())
            ).all()
        )

    @staticmethod
    def get_bot(tenant_id: str, bot_id: str) -> ChannelIntegrationBot:
        bot = db.session.scalar(
            select(ChannelIntegrationBot).where(
                ChannelIntegrationBot.tenant_id == tenant_id,
                ChannelIntegrationBot.id == bot_id,
            )
        )
        if not bot:
            raise ValueError("Channel integration bot is not found")
        return bot

    @staticmethod
    def list_bindings(tenant_id: str, bot_id: str) -> list[ChannelIntegrationAppBinding]:
        return list(
            db.session.scalars(
                select(ChannelIntegrationAppBinding)
                .where(
                    ChannelIntegrationAppBinding.tenant_id == tenant_id,
                    ChannelIntegrationAppBinding.bot_id == bot_id,
                )
                .order_by(ChannelIntegrationAppBinding.priority.asc(), ChannelIntegrationAppBinding.created_at.asc())
            ).all()
        )

    @classmethod
    def create_bot(cls, tenant_id: str, payload: dict[str, Any]) -> ChannelIntegrationBot:
        cls._validate_payload(payload, creating=True)
        bot = ChannelIntegrationBot(
            tenant_id=tenant_id,
            name=payload["name"].strip(),
            channel=payload.get("channel") or ChannelIntegrationType.FEISHU.value,
            enabled=bool(payload.get("enabled", True)),
            app_id=payload["app_id"].strip(),
            encrypted_app_secret=encrypt_token(tenant_id, payload["app_secret"]),
            encrypted_verification_token=encrypt_token(tenant_id, payload["verification_token"]),
            encrypted_encrypt_key=encrypt_token(tenant_id, payload["encrypt_key"]),
            bot_name=(payload.get("bot_name") or "").strip() or None,
            bot_open_id=(payload.get("bot_open_id") or "").strip() or None,
            callback_token=secrets.token_urlsafe(32),
        )
        db.session.add(bot)
        db.session.flush()
        cls.replace_bindings(tenant_id, bot.id, payload.get("bindings") or [])
        db.session.commit()
        return bot

    @classmethod
    def update_bot(cls, tenant_id: str, bot_id: str, payload: dict[str, Any]) -> ChannelIntegrationBot:
        bot = cls.get_bot(tenant_id, bot_id)
        cls._validate_payload(payload, creating=False)
        bot.name = payload["name"].strip()
        bot.channel = payload.get("channel") or ChannelIntegrationType.FEISHU.value
        bot.enabled = bool(payload.get("enabled", True))
        bot.app_id = payload["app_id"].strip()
        bot.bot_name = (payload.get("bot_name") or "").strip() or None
        bot.bot_open_id = (payload.get("bot_open_id") or "").strip() or None
        if payload.get("app_secret") and payload.get("app_secret") != HIDDEN_VALUE:
            bot.encrypted_app_secret = encrypt_token(tenant_id, payload["app_secret"])
        if payload.get("verification_token") and payload.get("verification_token") != HIDDEN_VALUE:
            bot.encrypted_verification_token = encrypt_token(tenant_id, payload["verification_token"])
        if payload.get("encrypt_key") and payload.get("encrypt_key") != HIDDEN_VALUE:
            bot.encrypted_encrypt_key = encrypt_token(tenant_id, payload["encrypt_key"])
        cls.replace_bindings(tenant_id, bot.id, payload.get("bindings") or [])
        db.session.commit()
        return bot

    @classmethod
    def delete_bot(cls, tenant_id: str, bot_id: str) -> None:
        bot = cls.get_bot(tenant_id, bot_id)
        db.session.delete(bot)
        db.session.commit()

    @classmethod
    def replace_bindings(cls, tenant_id: str, bot_id: str, bindings: list[dict[str, Any]]) -> None:
        db.session.execute(
            delete(ChannelIntegrationAppBinding).where(
                ChannelIntegrationAppBinding.tenant_id == tenant_id,
                ChannelIntegrationAppBinding.bot_id == bot_id,
            )
        )
        seen: set[str] = set()
        for index, binding in enumerate(bindings):
            purpose = (binding.get("purpose") or "").strip()
            app_id = (binding.get("app_id") or "").strip()
            if not purpose or not app_id:
                continue
            if purpose in seen:
                raise ValueError(f"Duplicate binding purpose: {purpose}")
            if purpose not in {item.value for item in ChannelIntegrationBindingPurpose}:
                raise ValueError(f"Unsupported binding purpose: {purpose}")
            app = db.session.scalar(select(App).where(App.tenant_id == tenant_id, App.id == app_id))
            if not app:
                raise ValueError("Bound app is not found in current workspace")
            seen.add(purpose)
            db.session.add(
                ChannelIntegrationAppBinding(
                    tenant_id=tenant_id,
                    bot_id=bot_id,
                    app_id=app_id,
                    purpose=purpose,
                    priority=index,
                )
            )

    @classmethod
    def get_runtime_config(cls, bot_id: str, callback_token: str | None = None) -> dict[str, Any]:
        bot = db.session.get(ChannelIntegrationBot, bot_id)
        if not bot:
            raise ValueError("Channel integration bot is not found")
        if not callback_token or bot.callback_token != callback_token:
            raise PermissionError("Invalid channel integration callback token")
        bindings = cls.list_bindings(bot.tenant_id, bot.id)
        apps: dict[str, Any] = {}
        for binding in bindings:
            app = db.session.get(App, binding.app_id)
            token = db.session.scalar(
                select(ApiToken)
                .where(ApiToken.app_id == binding.app_id, ApiToken.type == ApiTokenType.APP)
                .order_by(ApiToken.created_at.asc())
                .limit(1)
            )
            apps[binding.purpose] = {
                "app_id": binding.app_id,
                "app_name": app.name if app else "",
                "api_key": token.token if token else None,
            }
        return {
            "id": bot.id,
            "tenant_id": bot.tenant_id,
            "name": bot.name,
            "channel": bot.channel,
            "enabled": bot.enabled,
            "app_id": bot.app_id,
            "app_secret": decrypt_token(bot.tenant_id, bot.encrypted_app_secret),
            "verification_token": decrypt_token(bot.tenant_id, bot.encrypted_verification_token),
            "encrypt_key": decrypt_token(bot.tenant_id, bot.encrypted_encrypt_key),
            "bot_name": bot.bot_name,
            "bot_open_id": bot.bot_open_id,
            "bindings": apps,
        }

    @classmethod
    def mark_verified(cls, bot_id: str) -> None:
        bot = db.session.get(ChannelIntegrationBot, bot_id)
        if bot:
            bot.last_verified_at = datetime.utcnow()
            db.session.commit()

    @staticmethod
    def _validate_payload(payload: dict[str, Any], creating: bool) -> None:
        if not (payload.get("name") or "").strip():
            raise ValueError("name must not be empty")
        if (payload.get("channel") or ChannelIntegrationType.FEISHU.value) != ChannelIntegrationType.FEISHU.value:
            raise ValueError("Only feishu channel is supported")
        if not (payload.get("app_id") or "").strip():
            raise ValueError("app_id must not be empty")
        for field in SECRET_FIELDS:
            value = payload.get(field)
            if creating and not value:
                raise ValueError(f"{field} must not be empty")
            if value and value != HIDDEN_VALUE and len(value) < 3:
                raise ValueError(f"{field} is too short")
        if bool(payload.get("enabled", True)):
            has_default_binding = any(
                (binding.get("purpose") or "").strip() == ChannelIntegrationBindingPurpose.DEFAULT.value
                and (binding.get("app_id") or "").strip()
                for binding in payload.get("bindings") or []
            )
            if not has_default_binding:
                raise ValueError("enabled channel integration bot requires a default Dify app binding")
