from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager
from typing import Any, AsyncIterator

from fastapi import FastAPI, HTTPException, Query, Request

from .catalog import MaterialCatalog
from .config import get_settings
from .dify_metadata import DifyMetadataRepository, FileTextReader
from .mcp import MaterialMCPServer

logger = logging.getLogger(__name__)
settings = get_settings()
catalog = MaterialCatalog(
    settings.app_root,
    settings.db_path,
    settings.max_hash_bytes,
    settings.max_scan_files,
)
metadata_repo = DifyMetadataRepository(settings)
file_reader = FileTextReader(settings.app_root)
mcp_server = MaterialMCPServer(settings, catalog, metadata_repo)


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
    version="0.2.0",
    description="Read-only Dify material catalog and MCP evidence tools for the 资料全知agent.",
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
        "mcp_endpoint": "/mcp",
    }


@app.post("/mcp")
async def mcp_endpoint(request: Request) -> dict[str, Any]:
    payload = await request.json()
    if not isinstance(payload, dict):
        return {"jsonrpc": "2.0", "id": None, "error": {"code": -32600, "message": "Invalid MCP request"}}
    return mcp_server.handle(payload)


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


@app.get("/v1/materials/files")
def search_files(
    query: str | None = None,
    extension: str | None = None,
    limit: int = Query(50, ge=1, le=500),
) -> dict[str, object]:
    return catalog.search_files(query=query, extension=extension, limit=limit)


@app.get("/v1/materials/file-text")
def read_file_text(relative_path: str, max_chars: int = Query(12000, ge=1, le=50000)) -> dict[str, object]:
    try:
        return file_reader.read_file_text(relative_path, max_chars=max_chars)
    except (FileNotFoundError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/v1/datasets")
def list_datasets(limit: int = Query(50, ge=1, le=200)) -> dict[str, object]:
    return {"datasets": metadata_repo.list_datasets(limit=limit)}


@app.get("/v1/datasets/{dataset_id}/documents")
def list_dataset_documents(dataset_id: str, limit: int = Query(100, ge=1, le=500)) -> dict[str, object]:
    return {"documents": metadata_repo.list_dataset_documents(dataset_id=dataset_id, limit=limit)}


@app.get("/v1/documents")
def list_documents(
    dataset_id: str | None = None,
    query: str | None = None,
    limit: int = Query(100, ge=1, le=500),
) -> dict[str, object]:
    return {"documents": metadata_repo.list_documents(dataset_id=dataset_id, query=query, limit=limit)}


@app.get("/v1/segments/search")
def search_segments(
    query: str,
    dataset_id: str | None = None,
    document_id: str | None = None,
    limit: int = Query(10, ge=1, le=50),
) -> dict[str, object]:
    return {
        "query": query,
        "hits": metadata_repo.search_segments(query=query, dataset_id=dataset_id, document_id=document_id, limit=limit),
    }


@app.get("/v1/documents/{document_id}/chunks")
def read_document_chunks(
    document_id: str,
    center_position: int | None = None,
    before: int = Query(2, ge=0, le=10),
    after: int = Query(2, ge=0, le=10),
    limit: int = Query(20, ge=1, le=100),
) -> dict[str, object]:
    return metadata_repo.read_document_chunks(
        document_id=document_id,
        center_position=center_position,
        before=before,
        after=after,
        limit=limit,
    )


@app.get("/v1/apps")
def list_apps(limit: int = Query(50, ge=1, le=200)) -> dict[str, object]:
    return {"apps": metadata_repo.list_apps(limit=limit)}
