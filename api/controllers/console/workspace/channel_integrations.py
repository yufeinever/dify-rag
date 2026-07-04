from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from flask import request
from flask_restx import Resource
from pydantic import BaseModel, Field, field_validator
from werkzeug.exceptions import Forbidden, NotFound

from constants import HIDDEN_VALUE
from controllers.common.schema import register_response_schema_models, register_schema_models
from controllers.console import console_ns
from controllers.console.wraps import account_initialization_required, edit_permission_required, setup_required
from fields.base import ResponseModel
from libs.helper import to_timestamp
from libs.login import current_account_with_tenant, login_required
from models.channel_integration import ChannelIntegrationAppBinding, ChannelIntegrationBot
from models.model import App
from services.channel_integration_service import ChannelIntegrationService


class ChannelIntegrationBindingPayload(BaseModel):
    purpose: str
    app_id: str


class ChannelIntegrationBotPayload(BaseModel):
    name: str
    channel: str = "feishu"
    enabled: bool = True
    app_id: str
    app_secret: str = HIDDEN_VALUE
    verification_token: str = HIDDEN_VALUE
    encrypt_key: str = HIDDEN_VALUE
    bot_name: str | None = None
    bot_open_id: str | None = None
    bindings: list[ChannelIntegrationBindingPayload] = Field(default_factory=list)


class ChannelIntegrationBindingResponse(ResponseModel):
    id: str | None = None
    purpose: str
    app_id: str
    app_name: str | None = None


class ChannelIntegrationBotResponse(ResponseModel):
    id: str
    name: str
    channel: str
    enabled: bool
    app_id: str
    app_secret_configured: bool
    verification_token_configured: bool
    encrypt_key_configured: bool
    bot_name: str | None = None
    bot_open_id: str | None = None
    callback_url: str
    callback_token: str
    bindings: list[ChannelIntegrationBindingResponse]
    last_verified_at: int | None = None
    created_at: int | None = None
    updated_at: int | None = None

    @field_validator("created_at", "updated_at", "last_verified_at", mode="before")
    @classmethod
    def _normalize_timestamp(cls, value: datetime | int | None) -> int | None:
        return to_timestamp(value)


class ChannelIntegrationRuntimeResponse(ResponseModel):
    id: str
    tenant_id: str
    name: str
    channel: str
    enabled: bool
    app_id: str
    app_secret: str
    verification_token: str
    encrypt_key: str
    bot_name: str | None = None
    bot_open_id: str | None = None
    bindings: dict[str, Any]


register_schema_models(
    console_ns,
    ChannelIntegrationBindingPayload,
    ChannelIntegrationBotPayload,
    ChannelIntegrationBindingResponse,
    ChannelIntegrationBotResponse,
    ChannelIntegrationRuntimeResponse,
)
register_response_schema_models(console_ns, ChannelIntegrationBotResponse, ChannelIntegrationRuntimeResponse)


def _callback_url(bot: ChannelIntegrationBot) -> str:
    return f"/feishu-bot/events/{bot.id}?token={bot.callback_token}"


def _serialize_binding(binding: ChannelIntegrationAppBinding) -> dict[str, Any]:
    app = App.query.get(binding.app_id)
    return ChannelIntegrationBindingResponse(
        id=binding.id,
        purpose=binding.purpose,
        app_id=binding.app_id,
        app_name=app.name if app else None,
    ).model_dump(mode="json")


def _serialize_bot(bot: ChannelIntegrationBot) -> dict[str, Any]:
    bindings = ChannelIntegrationService.list_bindings(bot.tenant_id, bot.id)
    return ChannelIntegrationBotResponse(
        id=bot.id,
        name=bot.name,
        channel=bot.channel,
        enabled=bot.enabled,
        app_id=bot.app_id,
        app_secret_configured=bool(bot.encrypted_app_secret),
        verification_token_configured=bool(bot.encrypted_verification_token),
        encrypt_key_configured=bool(bot.encrypted_encrypt_key),
        bot_name=bot.bot_name,
        bot_open_id=bot.bot_open_id,
        callback_url=_callback_url(bot),
        callback_token=bot.callback_token,
        bindings=[_serialize_binding(binding) for binding in bindings],
        last_verified_at=bot.last_verified_at,
        created_at=bot.created_at,
        updated_at=bot.updated_at,
    ).model_dump(mode="json")


@console_ns.route("/workspaces/current/channel-integrations/bots")
class ChannelIntegrationBotListApi(Resource):
    @setup_required
    @login_required
    @account_initialization_required
    def get(self):
        _, tenant_id = current_account_with_tenant()
        return [_serialize_bot(bot) for bot in ChannelIntegrationService.list_bots(tenant_id)]

    @setup_required
    @login_required
    @account_initialization_required
    @edit_permission_required
    def post(self):
        payload = ChannelIntegrationBotPayload.model_validate(console_ns.payload or {})
        _, tenant_id = current_account_with_tenant()
        bot = ChannelIntegrationService.create_bot(tenant_id, payload.model_dump())
        return _serialize_bot(bot), 201


@console_ns.route("/workspaces/current/channel-integrations/bots/<uuid:bot_id>")
class ChannelIntegrationBotDetailApi(Resource):
    @setup_required
    @login_required
    @account_initialization_required
    def get(self, bot_id: UUID):
        _, tenant_id = current_account_with_tenant()
        return _serialize_bot(ChannelIntegrationService.get_bot(tenant_id, str(bot_id)))

    @setup_required
    @login_required
    @account_initialization_required
    @edit_permission_required
    def post(self, bot_id: UUID):
        payload = ChannelIntegrationBotPayload.model_validate(console_ns.payload or {})
        _, tenant_id = current_account_with_tenant()
        bot = ChannelIntegrationService.update_bot(tenant_id, str(bot_id), payload.model_dump())
        return _serialize_bot(bot)

    @setup_required
    @login_required
    @account_initialization_required
    @edit_permission_required
    def delete(self, bot_id: UUID):
        _, tenant_id = current_account_with_tenant()
        ChannelIntegrationService.delete_bot(tenant_id, str(bot_id))
        return "", 204


@console_ns.route("/workspaces/current/channel-integrations/runtime/bots/<uuid:bot_id>")
class ChannelIntegrationRuntimeBotApi(Resource):
    def get(self, bot_id: UUID):
        token = request.headers.get("X-Channel-Integration-Token") or request.args.get("token")
        try:
            runtime = ChannelIntegrationService.get_runtime_config(str(bot_id), token)
        except PermissionError as exc:
            raise Forbidden(str(exc)) from exc
        except ValueError as exc:
            raise NotFound(str(exc)) from exc
        return ChannelIntegrationRuntimeResponse.model_validate(runtime).model_dump(mode="json")


@console_ns.route("/workspaces/current/channel-integrations/runtime/bots/<uuid:bot_id>/verified")
class ChannelIntegrationRuntimeVerifiedApi(Resource):
    def post(self, bot_id: UUID):
        token = request.headers.get("X-Channel-Integration-Token") or request.args.get("token")
        try:
            ChannelIntegrationService.get_runtime_config(str(bot_id), token)
        except PermissionError as exc:
            raise Forbidden(str(exc)) from exc
        except ValueError as exc:
            raise NotFound(str(exc)) from exc
        ChannelIntegrationService.mark_verified(str(bot_id))
        return {"result": "success"}
