from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime settings for the read-only material catalog service.

    The service is intentionally scoped to the mounted Dify app volume. All configured scan roots are resolved under
    `app_root`; absolute paths and parent traversal are rejected before scanning.
    """

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_root: Path = Field(Path("/dify-app"), alias="MATERIAL_CATALOG_APP_ROOT")
    allowed_roots: str = Field("storage,.", alias="MATERIAL_CATALOG_ALLOWED_ROOTS")
    db_path: Path = Field(Path("/app/catalog/material_catalog.sqlite"), alias="MATERIAL_CATALOG_DB_PATH")
    sync_interval_seconds: int = Field(3600, alias="MATERIAL_CATALOG_SYNC_INTERVAL_SECONDS")
    max_hash_bytes: int = Field(536870912, alias="MATERIAL_CATALOG_MAX_HASH_BYTES")
    max_scan_files: int = Field(20000, alias="MATERIAL_CATALOG_MAX_SCAN_FILES")

    dify_db_host: str = Field("db_postgres", alias="DIFY_DB_HOST")
    dify_db_port: int = Field(5432, alias="DIFY_DB_PORT")
    dify_db_name: str = Field("dify", alias="DIFY_DB_NAME")
    dify_db_user: str = Field("postgres", alias="DIFY_DB_USER")
    dify_db_password: str = Field("", alias="DIFY_DB_PASSWORD")
    dify_files_url: str = Field("", alias="DIFY_FILES_URL")
    dify_file_preview_secret_key: str = Field("", alias="DIFY_FILE_PREVIEW_SECRET_KEY")
    dify_file_preview_ttl_seconds: int = Field(300, alias="DIFY_FILE_PREVIEW_TTL_SECONDS")

    @field_validator("sync_interval_seconds")
    @classmethod
    def validate_sync_interval(cls, value: int) -> int:
        if value < 60:
            raise ValueError("sync interval must be at least 60 seconds")
        return value

    @property
    def scan_roots(self) -> list[str]:
        roots = [item.strip() for item in self.allowed_roots.split(",") if item.strip()]
        return roots or ["storage"]


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    settings = Settings()
    settings.db_path.parent.mkdir(parents=True, exist_ok=True)
    return settings
