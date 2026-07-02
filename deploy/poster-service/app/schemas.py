from __future__ import annotations

from typing import Literal
from pydantic import BaseModel, Field, field_validator


class PosterAsset(BaseModel):
    url: str | None = None
    title: str | None = None
    description: str | None = None
    tags: list[str] = Field(default_factory=list)


class PosterBrief(BaseModel):
    theme: str = Field(..., min_length=1, description="Poster topic or campaign theme")
    background: str | None = Field(None, description="Desired background style")
    special_elements: list[str] = Field(default_factory=list, description="Festival or decorative elements")
    audience: str | None = Field(None, description="Target audience")
    main_title: str | None = Field(None, description="Main poster title")
    subtitle: str | None = Field(None, description="Secondary copy")
    selling_points: list[str] = Field(default_factory=list, description="Short benefit bullets")
    brand_constraints: str | None = Field(None, description="Brand, compliance, or visual restrictions")


class GeneratePosterRequest(BaseModel):
    brief: PosterBrief
    assets: list[PosterAsset] = Field(default_factory=list)
    size: str = Field("1080x1440", description="Final output size in WIDTHxHEIGHT format")
    overlay_text: bool = Field(True, description="Overlay Chinese title/copy with deterministic layout")
    request_id: str | None = Field(None, description="Caller-provided trace id")
    user_query: str | None = Field(None, description="Original user request from Dify")
    optimized_prompt: str | None = Field(None, description="Display-ready optimized image prompt from Dify")

    @field_validator("size")
    @classmethod
    def validate_size(cls, value: str) -> str:
        parts = value.lower().split("x")
        if len(parts) != 2 or not all(part.isdigit() for part in parts):
            raise ValueError("size must be WIDTHxHEIGHT, for example 1080x1440")
        width, height = (int(parts[0]), int(parts[1]))
        if width < 512 or height < 512 or width > 4096 or height > 4096:
            raise ValueError("size must be between 512 and 4096 pixels per side")
        return f"{width}x{height}"


PosterStatus = Literal["queued", "running", "succeeded", "failed"]


class GeneratePosterResponse(BaseModel):
    status: Literal["succeeded", "failed"]
    poster_url: str | None = None
    thumbnail_url: str | None = None
    used_assets: list[PosterAsset] = Field(default_factory=list)
    final_prompt: str
    size: str
    request_id: str
    error: str | None = None


class PosterJobResponse(BaseModel):
    status: PosterStatus
    job_id: str
    request_id: str
    final_prompt: str
    size: str
    estimated_time_text: str = "图片生成预计需要 5-10 分钟左右。"
    poster_url: str | None = None
    thumbnail_url: str | None = None
    used_assets: list[PosterAsset] = Field(default_factory=list)
    error: str | None = None
