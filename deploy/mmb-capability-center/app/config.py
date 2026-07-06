from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import AnyHttpUrl, Field, HttpUrl
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    auth_token: str | None = Field(default=None, alias="CAPABILITY_AUTH_TOKEN")
    db_path: Path = Field(default=Path("./data/capability_center.sqlite"), alias="CAPABILITY_DB_PATH")
    material_catalog_url: AnyHttpUrl = Field(default="http://material-catalog-service:8091", alias="MATERIAL_CATALOG_URL")
    poster_service_url: AnyHttpUrl = Field(default="http://poster-service:8088", alias="POSTER_SERVICE_URL")
    dify_base_url: AnyHttpUrl = Field(default="http://nginx/v1", alias="DIFY_BASE_URL")
    dify_default_app_api_key: str | None = Field(default=None, alias="DIFY_DEFAULT_APP_API_KEY")
    dify_copywriting_app_api_key: str | None = Field(default=None, alias="DIFY_COPYWRITING_APP_API_KEY")
    dify_business_artifact_app_api_key: str | None = Field(default=None, alias="DIFY_BUSINESS_ARTIFACT_APP_API_KEY")
    dify_office_app_api_key: str | None = Field(default=None, alias="DIFY_OFFICE_APP_API_KEY")
    dify_visual_ppt_app_api_key: str | None = Field(default=None, alias="DIFY_VISUAL_PPT_APP_API_KEY")
    http_timeout_seconds: float = Field(default=120.0, alias="CAPABILITY_HTTP_TIMEOUT_SECONDS")
    feishu_app_id: str | None = Field(default=None, alias="FEISHU_APP_ID")
    feishu_app_secret: str | None = Field(default=None, alias="FEISHU_APP_SECRET")
    feishu_api_base_url: HttpUrl = Field(default="https://open.feishu.cn/open-apis", alias="FEISHU_API_BASE_URL")
    poster_delivery_enabled: bool = Field(default=True, alias="POSTER_DELIVERY_ENABLED")
    poster_delivery_poll_interval_seconds: float = Field(default=15.0, alias="POSTER_DELIVERY_POLL_INTERVAL_SECONDS")
    poster_delivery_batch_size: int = Field(default=10, alias="POSTER_DELIVERY_BATCH_SIZE")
    poster_delivery_max_attempts: int = Field(default=80, alias="POSTER_DELIVERY_MAX_ATTEMPTS")
    hermes_state_db_path: Path | None = Field(default=None, alias="HERMES_STATE_DB_PATH")


@lru_cache
def get_settings() -> Settings:
    return Settings()
