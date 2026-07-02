from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    public_base_url: str = Field("http://localhost:8088", alias="POSTER_PUBLIC_BASE_URL")
    output_dir: Path = Field(Path("/app/output"), alias="POSTER_OUTPUT_DIR")
    default_size: str = Field("1080x1440", alias="POSTER_DEFAULT_SIZE")
    llm_model: str = Field("gpt-5.5", alias="POSTER_LLM_MODEL")
    image_model: str = Field("gpt-5.5", alias="POSTER_IMAGE_MODEL")
    image_mode: str = Field("responses", alias="POSTER_IMAGE_MODE")
    image_size: str = Field("1024x1536", alias="POSTER_IMAGE_SIZE")
    openai_base_url: str = Field("https://api.openai.com", alias="POSTER_OPENAI_BASE_URL")
    allow_mock_openai: bool = Field(False, alias="POSTER_ALLOW_MOCK_OPENAI")
    openai_api_key: str | None = Field(None, alias="OPENAI_API_KEY")


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    settings = Settings()
    settings.output_dir.mkdir(parents=True, exist_ok=True)
    return settings
