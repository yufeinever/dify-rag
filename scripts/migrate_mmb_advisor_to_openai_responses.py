from __future__ import annotations

import json
import os
from typing import Any

from app import app
from core.helper import encrypter
from extensions.ext_database import db
from graphon.model_runtime.entities.model_entities import ModelType
from models.model import App
from models.provider import Provider, ProviderCredential, ProviderModel, ProviderModelCredential, ProviderType
from services.model_provider_service import ModelProviderService
from sqlalchemy import select

TENANT_ID = os.environ.get("DIFY_TENANT_ID", "60630e96-a41c-481d-92e2-c6f83c9e4749")
APP_NAME = os.environ.get("APP_NAME", "MMB智囊")
MODEL_NAME = os.environ.get("MODEL_NAME", "gpt-5.5")
OLD_PROVIDER = os.environ.get(
    "OLD_PROVIDER",
    "langgenius/openai_api_compatible/openai_api_compatible",
)
NEW_PROVIDER = os.environ.get(
    "NEW_PROVIDER",
    "mmb/openai_responses_provider/openai_responses_provider",
)


def _masked(value: str | None) -> str:
    if not value:
        return "<empty>"
    if len(value) <= 8:
        return "<set>"
    return value[:3] + "***" + value[-3:]


def _old_model_record() -> ProviderModel:
    record = db.session.scalar(
        select(ProviderModel).where(
            ProviderModel.tenant_id == TENANT_ID,
            ProviderModel.provider_name == OLD_PROVIDER,
            ProviderModel.model_name == MODEL_NAME,
            ProviderModel.model_type == ModelType.LLM,
        )
    )
    if not record or not record.credential_id:
        raise RuntimeError(f"Old model credential not found for {OLD_PROVIDER}/{MODEL_NAME}")
    return record


def _decrypt_old_credentials(record: ProviderModel) -> dict[str, Any]:
    credential = db.session.scalar(
        select(ProviderModelCredential).where(
            ProviderModelCredential.id == record.credential_id,
            ProviderModelCredential.tenant_id == TENANT_ID,
        )
    )
    if not credential or not credential.encrypted_config:
        raise RuntimeError(f"Old model credential config not found: {record.credential_id}")
    raw = json.loads(credential.encrypted_config)
    api_key = raw.get("api_key")
    if not api_key:
        raise RuntimeError("Old credential has no api_key")
    raw["api_key"] = encrypter.decrypt_token(TENANT_ID, api_key)
    return raw


def _build_new_credentials(old: dict[str, Any]) -> dict[str, Any]:
    endpoint = os.environ.get("MMB_OPENAI_RESPONSES_API_BASE") or old.get("endpoint_url") or old.get("api_base")
    api_key = os.environ.get("MMB_OPENAI_RESPONSES_API_KEY") or old.get("api_key")
    if not endpoint:
        raise RuntimeError("MMB_OPENAI_RESPONSES_API_BASE is missing and old endpoint_url is empty")
    if not api_key:
        raise RuntimeError("MMB_OPENAI_RESPONSES_API_KEY is missing and old api_key is empty")
    return {
        "openai_api_key": api_key,
        "openai_api_base": endpoint,
        "validate_model": MODEL_NAME,
        "api_protocol": "responses",
        "enable_web_search": os.environ.get("ENABLE_WEB_SEARCH", "enabled"),
        "enable_code_interpreter": os.environ.get("ENABLE_CODE_INTERPRETER", "disabled"),
        "enable_file_search": os.environ.get("ENABLE_FILE_SEARCH", "disabled"),
        "openai_vector_store_ids": os.environ.get("OPENAI_VECTOR_STORE_IDS", ""),
        "enable_material_mcp": os.environ.get("ENABLE_MATERIAL_MCP", "disabled"),
        "material_mcp_server_url": os.environ.get("MATERIAL_MCP_SERVER_URL", ""),
        "material_mcp_auth_token": os.environ.get("MATERIAL_MCP_AUTH_TOKEN", ""),
        "material_mcp_allowed_tools": os.environ.get(
            "MATERIAL_MCP_ALLOWED_TOOLS",
            "server_info,list_material_roots,list_datasets,list_documents,search_segments,"
            "read_document_chunks,search_files,search_visual_assets,find_person_visual_candidates,"
            "read_file_text,profile_materials,list_material_changes",
        ),
    }


def _upsert_provider_credential(credentials: dict[str, Any]) -> None:
    """Configure provider-level credentials for predefined OpenAI models.

    The private plugin exposes gpt-5.5 as a predefined model, so Dify marks the
    model active only when provider-level credentials exist. Model-level
    credentials are still useful for customizable models, but they do not change
    predefined model status.
    """
    service = ModelProviderService()
    credential_name = "remote-gpt-5.5-responses"
    provider_record = db.session.scalar(
        select(Provider).where(
            Provider.tenant_id == TENANT_ID,
            Provider.provider_name == NEW_PROVIDER,
            Provider.provider_type == ProviderType.CUSTOM,
        )
    )
    if provider_record and provider_record.credential_id:
        service.update_provider_credential(
            TENANT_ID,
            NEW_PROVIDER,
            credentials,
            provider_record.credential_id,
            credential_name,
        )
        return

    existing_credential = db.session.scalar(
        select(ProviderCredential).where(
            ProviderCredential.tenant_id == TENANT_ID,
            ProviderCredential.provider_name == NEW_PROVIDER,
            ProviderCredential.credential_name == credential_name,
        )
    )
    if existing_credential:
        service.update_provider_credential(
            TENANT_ID,
            NEW_PROVIDER,
            credentials,
            existing_credential.id,
            credential_name,
        )
        service.switch_active_provider_credential(TENANT_ID, NEW_PROVIDER, existing_credential.id)
        return

    service.create_provider_credential(TENANT_ID, NEW_PROVIDER, credentials, credential_name)


def _upsert_model_credential(credentials: dict[str, Any]) -> None:
    service = ModelProviderService()
    existing = db.session.scalar(
        select(ProviderModel).where(
            ProviderModel.tenant_id == TENANT_ID,
            ProviderModel.provider_name == NEW_PROVIDER,
            ProviderModel.model_name == MODEL_NAME,
            ProviderModel.model_type == ModelType.LLM,
        )
    )
    if existing and existing.credential_id:
        service.update_model_credential(
            TENANT_ID,
            NEW_PROVIDER,
            "llm",
            MODEL_NAME,
            credentials,
            existing.credential_id,
            "remote-gpt-5.5-responses",
        )
    else:
        service.create_model_credential(
            TENANT_ID,
            NEW_PROVIDER,
            "llm",
            MODEL_NAME,
            credentials,
            "remote-gpt-5.5-responses",
        )


def _switch_app_model() -> dict[str, Any]:
    app_obj = db.session.scalar(select(App).where(App.tenant_id == TENANT_ID, App.name == APP_NAME).order_by(App.created_at.desc()))
    if not app_obj or not app_obj.app_model_config:
        raise RuntimeError(f"App not found or model config missing: {APP_NAME}")
    config = app_obj.app_model_config
    old_model = json.loads(config.model or "{}") if config.model else {}
    config.model = json.dumps(
        {
            "provider": NEW_PROVIDER,
            "name": MODEL_NAME,
            "mode": "chat",
            "completion_params": old_model.get("completion_params", {"stop": []}),
        },
        ensure_ascii=False,
    )
    config.provider = NEW_PROVIDER
    config.model_id = MODEL_NAME
    db.session.commit()
    return {"app_id": app_obj.id, "old_model": old_model, "new_provider": NEW_PROVIDER, "model": MODEL_NAME}


def main() -> None:
    with app.app_context():
        old_record = _old_model_record()
        old_credentials = _decrypt_old_credentials(old_record)
        new_credentials = _build_new_credentials(old_credentials)
        safe = {
            "openai_api_base": new_credentials.get("openai_api_base"),
            "openai_api_key": _masked(new_credentials.get("openai_api_key")),
            "enable_web_search": new_credentials.get("enable_web_search"),
            "enable_code_interpreter": new_credentials.get("enable_code_interpreter"),
            "enable_file_search": new_credentials.get("enable_file_search"),
            "enable_material_mcp": new_credentials.get("enable_material_mcp"),
            "material_mcp_server_url": new_credentials.get("material_mcp_server_url"),
            "material_mcp_auth_token": _masked(new_credentials.get("material_mcp_auth_token")),
        }
        print(json.dumps({"action": "validate_new_provider", "safe_credentials": safe}, ensure_ascii=False), flush=True)
        _upsert_provider_credential(new_credentials)
        _upsert_model_credential(new_credentials)
        switched = _switch_app_model()
        print(json.dumps({"configured": True, **switched}, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
