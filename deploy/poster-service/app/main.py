from __future__ import annotations

import uuid
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from PIL import Image

from .config import get_settings
from .openai_client import OpenAIImageClient
from .prompting import build_prompt
from .renderer import compose_poster
from .schemas import GeneratePosterRequest, GeneratePosterResponse

app = FastAPI(
    title="MMB Poster Service",
    version="0.1.0",
    description="Dify OpenAPI tool service for GPT-5.5 planned poster generation with deterministic Chinese text overlays.",
)
settings = get_settings()
app.mount("/files", StaticFiles(directory=settings.output_dir), name="files")


@app.get("/health")
def health() -> dict[str, object]:
    return {
        "status": "ok",
        "llm_model": settings.llm_model,
        "image_model": settings.image_model,
        "image_mode": settings.image_mode,
        "openai_configured": bool(settings.openai_api_key),
    }


@app.post("/v1/posters", response_model=GeneratePosterResponse)
async def generate_poster(request: GeneratePosterRequest) -> GeneratePosterResponse:
    request_id = request.request_id or str(uuid.uuid4())
    final_prompt = build_prompt(request, settings.llm_model)
    try:
        background_bytes: bytes | None = None
        if settings.allow_mock_openai:
            background_bytes = None
        else:
            result = await OpenAIImageClient(settings).generate(request, final_prompt)
            background_bytes = result.image_bytes
        poster = compose_poster(background_bytes, request)
        poster_name = f"poster-{request_id}.png"
        thumb_name = f"poster-{request_id}-thumb.jpg"
        poster_path = settings.output_dir / poster_name
        thumb_path = settings.output_dir / thumb_name
        poster.save(poster_path, format="PNG", optimize=True)
        thumbnail = poster.copy()
        thumbnail.thumbnail((360, 480), Image.Resampling.LANCZOS)
        thumbnail.save(thumb_path, format="JPEG", quality=88, optimize=True)
        return GeneratePosterResponse(
            status="succeeded",
            poster_url=f"{settings.public_base_url.rstrip('/')}/files/{poster_name}",
            thumbnail_url=f"{settings.public_base_url.rstrip('/')}/files/{thumb_name}",
            used_assets=request.assets,
            final_prompt=final_prompt,
            size=request.size,
            request_id=request_id,
        )
    except Exception as exc:
        return GeneratePosterResponse(
            status="failed",
            used_assets=request.assets,
            final_prompt=final_prompt,
            size=request.size,
            request_id=request_id,
            error=str(exc),
        )


@app.get("/openapi-dify.yaml", response_model=None)
def dify_openapi_spec():
    spec_path = Path(__file__).resolve().parents[1] / "openapi-dify.yaml"
    if not spec_path.exists():
        return JSONResponse(status_code=404, content={"error": "openapi-dify.yaml not found"})
    return FileResponse(spec_path, media_type="application/yaml")
