from __future__ import annotations

import asyncio
import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import BackgroundTasks, FastAPI
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from PIL import Image

from .config import get_settings
from .openai_client import OpenAIImageClient
from .prompting import build_prompt
from .renderer import compose_poster
from .schemas import GeneratePosterRequest, GeneratePosterResponse, PosterJobResponse

app = FastAPI(
    title="MMB Poster Service",
    version="0.1.0",
    description="Dify OpenAPI tool service for GPT-5.5 planned poster generation with deterministic Chinese text overlays.",
)
settings = get_settings()
app.mount("/files", StaticFiles(directory=settings.output_dir), name="files")
_running_jobs: set[str] = set()
_job_lock = asyncio.Lock()


@app.get("/health")
def health() -> dict[str, object]:
    return {
        "status": "ok",
        "llm_model": settings.llm_model,
        "image_model": settings.image_model,
        "image_mode": settings.image_mode,
        "openai_configured": bool(settings.openai_api_key),
    }


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _job_path(job_id: str) -> Path:
    return settings.output_dir / "jobs" / f"{job_id}.json"


def _poster_urls(job_id: str) -> tuple[str, str]:
    base = settings.public_base_url.rstrip("/")
    return f"{base}/files/poster-{job_id}.png", f"{base}/files/poster-{job_id}-thumb.jpg"


def _read_job(job_id: str) -> dict[str, Any] | None:
    path = _job_path(job_id)
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _write_job(job_id: str, data: dict[str, Any]) -> None:
    path = _job_path(job_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    data["updated_at"] = _now_iso()
    tmp_path = path.with_suffix(".json.tmp")
    tmp_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp_path.replace(path)


def _display_prompt(request: GeneratePosterRequest, render_prompt: str) -> str:
    return request.optimized_prompt or request.brief.background or render_prompt


def _job_response(data: dict[str, Any]) -> PosterJobResponse:
    return PosterJobResponse(
        status=data.get("status", "failed"),
        job_id=data["job_id"],
        request_id=data.get("request_id") or data["job_id"],
        final_prompt=data.get("final_prompt") or "",
        size=data.get("size") or settings.default_size,
        poster_url=data.get("poster_url"),
        thumbnail_url=data.get("thumbnail_url"),
        used_assets=data.get("used_assets") or [],
        error=data.get("error"),
    )


async def _render_request(request: GeneratePosterRequest, request_id: str, final_prompt: str) -> GeneratePosterResponse:
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
    poster_url, thumbnail_url = _poster_urls(request_id)
    return GeneratePosterResponse(
        status="succeeded",
        poster_url=poster_url,
        thumbnail_url=thumbnail_url,
        used_assets=request.assets,
        final_prompt=final_prompt,
        size=request.size,
        request_id=request_id,
    )


async def _run_job(job_id: str, request: GeneratePosterRequest, final_prompt: str) -> None:
    async with _job_lock:
        if job_id in _running_jobs:
            return
        _running_jobs.add(job_id)
    try:
        data = _read_job(job_id) or {}
        data.update({"status": "running", "started_at": _now_iso(), "error": None})
        _write_job(job_id, data)
        result = await _render_request(request, job_id, final_prompt)
        data.update(
            {
                "status": "succeeded",
                "poster_url": result.poster_url,
                "thumbnail_url": result.thumbnail_url,
                "used_assets": [asset.model_dump() for asset in request.assets],
                "error": None,
            }
        )
        _write_job(job_id, data)
    except Exception as exc:
        data = _read_job(job_id) or {
            "job_id": job_id,
            "request_id": job_id,
            "final_prompt": final_prompt,
            "size": request.size,
            "used_assets": [asset.model_dump() for asset in request.assets],
        }
        data.update({"status": "failed", "error": str(exc)})
        _write_job(job_id, data)
    finally:
        async with _job_lock:
            _running_jobs.discard(job_id)


@app.post("/v1/posters", response_model=GeneratePosterResponse)
async def generate_poster(request: GeneratePosterRequest) -> GeneratePosterResponse:
    request_id = request.request_id or str(uuid.uuid4())
    final_prompt = build_prompt(request, settings.llm_model)
    try:
        return await _render_request(request, request_id, final_prompt)
    except Exception as exc:
        return GeneratePosterResponse(
            status="failed",
            used_assets=request.assets,
            final_prompt=final_prompt,
            size=request.size,
            request_id=request_id,
            error=str(exc),
        )


@app.post("/v1/poster-jobs", response_model=PosterJobResponse)
async def create_poster_job(request: GeneratePosterRequest, background_tasks: BackgroundTasks) -> PosterJobResponse:
    job_id = request.request_id or str(uuid.uuid4())
    render_prompt = build_prompt(request, settings.llm_model)
    display_prompt = _display_prompt(request, render_prompt)
    existing = _read_job(job_id)
    if existing:
        if existing.get("status") == "succeeded":
            return _job_response(existing)
        if existing.get("status") in {"queued", "running"}:
            return _job_response(existing)

    poster_url, thumbnail_url = _poster_urls(job_id)
    data: dict[str, Any] = {
        "status": "queued",
        "job_id": job_id,
        "request_id": job_id,
        "final_prompt": display_prompt,
        "render_prompt": render_prompt,
        "size": request.size,
        "poster_url": poster_url if (settings.output_dir / f"poster-{job_id}.png").exists() else None,
        "thumbnail_url": thumbnail_url if (settings.output_dir / f"poster-{job_id}-thumb.jpg").exists() else None,
        "used_assets": [asset.model_dump() for asset in request.assets],
        "created_at": _now_iso(),
        "error": None,
    }
    if data["poster_url"]:
        data["status"] = "succeeded"
        _write_job(job_id, data)
        return _job_response(data)
    _write_job(job_id, data)
    background_tasks.add_task(_run_job, job_id, request, render_prompt)
    return _job_response(data)


@app.get("/v1/poster-jobs/{job_id}", response_model=PosterJobResponse)
def get_poster_job(job_id: str) -> PosterJobResponse:
    data = _read_job(job_id)
    if not data:
        return PosterJobResponse(
            status="failed",
            job_id=job_id,
            request_id=job_id,
            final_prompt="",
            size=settings.default_size,
            error="任务不存在或已被清理，请重新生成。",
        )
    return _job_response(data)


@app.get("/openapi-dify.yaml", response_model=None)
def dify_openapi_spec():
    spec_path = Path(__file__).resolve().parents[1] / "openapi-dify.yaml"
    if not spec_path.exists():
        return JSONResponse(status_code=404, content={"error": "openapi-dify.yaml not found"})
    return FileResponse(spec_path, media_type="application/yaml")
