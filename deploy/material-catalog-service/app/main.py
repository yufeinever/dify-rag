from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI, HTTPException, Query

from .catalog import MaterialCatalog
from .config import get_settings
from .dify_metadata import DifyMetadataRepository

logger = logging.getLogger(__name__)
settings = get_settings()
catalog = MaterialCatalog(
    settings.app_root,
    settings.db_path,
    settings.max_hash_bytes,
    settings.max_scan_files,
)
metadata_repo = DifyMetadataRepository(settings)


async def _periodic_sync() -> None:
    while True:
        try:
            await asyncio.to_thread(catalog.sync, settings.scan_roots)
        except Exception:
            logger.exception("material catalog periodic sync failed")
        await asyncio.sleep(settings.sync_interval_seconds)


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    task = asyncio.create_task(_periodic_sync())
    try:
        yield
    finally:
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass


app = FastAPI(
    title="MMB Material Catalog Service",
    version="0.1.0",
    description="Read-only Dify material catalog tool service for the 资料全知agent.",
    lifespan=lifespan,
)


@app.get("/health")
def health() -> dict[str, object]:
    return {
        "status": "ok",
        "app_root": str(settings.app_root),
        "scan_roots": settings.scan_roots,
        "db_path": str(settings.db_path),
        "sync_interval_seconds": settings.sync_interval_seconds,
    }


@app.get("/v1/roots")
def list_material_roots() -> dict[str, object]:
    return {"roots": catalog.roots_summary(settings.scan_roots)}


@app.post("/v1/catalog/sync")
def sync_catalog() -> dict[str, object]:
    """Refresh the local catalog state without writing to Dify or source material directories."""

    try:
        return catalog.sync(settings.scan_roots)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/v1/materials/profile")
def profile_materials(limit: int = Query(100, ge=1, le=1000)) -> dict[str, object]:
    return catalog.profile(limit=limit)


@app.get("/v1/materials/changes")
def list_material_changes(limit: int = Query(100, ge=1, le=1000)) -> dict[str, object]:
    return catalog.changes(limit=limit)


@app.get("/v1/datasets")
def list_datasets(limit: int = Query(50, ge=1, le=200)) -> dict[str, object]:
    return {"datasets": metadata_repo.list_datasets(limit=limit)}


@app.get("/v1/datasets/{dataset_id}/documents")
def list_dataset_documents(dataset_id: str, limit: int = Query(100, ge=1, le=500)) -> dict[str, object]:
    return {"documents": metadata_repo.list_dataset_documents(dataset_id=dataset_id, limit=limit)}


@app.get("/v1/apps")
def list_apps(limit: int = Query(50, ge=1, le=200)) -> dict[str, object]:
    return {"apps": metadata_repo.list_apps(limit=limit)}
