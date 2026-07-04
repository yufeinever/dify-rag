from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import AnyHttpUrl, Field
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
    http_timeout_seconds: float = Field(default=120.0, alias="CAPABILITY_HTTP_TIMEOUT_SECONDS")


@lru_cache
def get_settings() -> Settings:
    return Settings()
