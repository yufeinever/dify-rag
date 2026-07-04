from __future__ import annotations

import uuid
from pathlib import Path
from typing import Any

from fastapi import Depends, FastAPI, Header, HTTPException, Query, Request, Response
from fastapi.responses import FileResponse

from .audit import AuditStore
from .clients import CapabilityClientError, ServiceClients
from .config import get_settings
from .models import (
    ContextResponse,
    CreateBusinessArtifactRequest,
    CreatePosterJobRequest,
    CreateTeamArtifactRequest,
    GenerateCopywritingRequest,
    ReadKnowledgeRequest,
    ReadMaterialRequest,
    ResourceScope,
    SearchEnterpriseKnowledgeRequest,
    SearchMaterialsRequest,
    ToolContext,
    ToolDescriptor,
    ToolResponse,
)
from .mcp_protocol import handle_mcp_request

settings = get_settings()
audit_store = AuditStore(settings.db_path)
clients = ServiceClients(settings)

app = FastAPI(
    title="MMB Capability Center",
    version="0.1.0",
    description="Unified tool API for MMB enterprise knowledge, materials, copywriting, posters, artifacts, audit, and shared context.",
)


def new_request_id() -> str:
    return str(uuid.uuid4())


async def require_auth(authorization: str | None = Header(default=None)) -> None:
    if not settings.auth_token:
        return
    expected = f"Bearer {settings.auth_token}"
    if authorization != expected:
        raise HTTPException(status_code=401, detail="invalid capability center token")


def tool_descriptors() -> list[ToolDescriptor]:
    return [
        ToolDescriptor(
            name="search_enterprise_knowledge",
            description="Search approved enterprise, department, or project knowledge before answering factual MMB questions.",
            resource_scopes=[ResourceScope.ENTERPRISE, ResourceScope.DEPARTMENT, ResourceScope.PROJECT],
            endpoint="/v1/knowledge/search",
        ),
        ToolDescriptor(
            name="read_knowledge",
            description="Read nearby chunks from an approved MMB knowledge document.",
            resource_scopes=[ResourceScope.ENTERPRISE, ResourceScope.DEPARTMENT, ResourceScope.PROJECT],
            endpoint="/v1/knowledge/read",
        ),
        ToolDescriptor(
            name="search_materials",
            description="Find MMB source materials, images, documents, and asset records by keyword or file extension.",
            resource_scopes=[ResourceScope.ENTERPRISE, ResourceScope.DEPARTMENT, ResourceScope.PROJECT],
            endpoint="/v1/materials/search",
        ),
        ToolDescriptor(
            name="read_material",
            description="Read text from a material file returned by search_materials.",
            resource_scopes=[ResourceScope.ENTERPRISE, ResourceScope.DEPARTMENT, ResourceScope.PROJECT],
            endpoint="/v1/materials/read",
        ),
        ToolDescriptor(
            name="create_business_artifact",
            description="Create or request a real MMB Word, Excel, PPT, or structured business artifact.",
            resource_scopes=[ResourceScope.ENTERPRISE, ResourceScope.DEPARTMENT, ResourceScope.PROJECT, ResourceScope.TEAM],
            endpoint="/v1/artifacts/business",
            side_effect=True,
        ),
        ToolDescriptor(
            name="generate_copywriting",
            description="Generate polished MMB copy for social posts, groups, campaigns, sales, or customer communication.",
            resource_scopes=[ResourceScope.ENTERPRISE, ResourceScope.DEPARTMENT, ResourceScope.PROJECT],
            endpoint="/v1/copywriting/generate",
        ),
        ToolDescriptor(
            name="create_poster_job",
            description="Create an asynchronous MMB poster job when the user asks for a poster or shareable campaign image.",
            resource_scopes=[ResourceScope.ENTERPRISE, ResourceScope.DEPARTMENT, ResourceScope.PROJECT],
            endpoint="/v1/poster-jobs",
            side_effect=True,
        ),
        ToolDescriptor(
            name="create_team_artifact",
            description="Save a confirmed copy, poster note, research summary, or task output into a team or project workspace.",
            resource_scopes=[ResourceScope.TEAM, ResourceScope.PROJECT, ResourceScope.PERSONAL],
            endpoint="/v1/artifacts/team",
            side_effect=True,
        ),
    ]


def sources_from_search(data: dict[str, Any]) -> list[dict[str, Any]]:
    hits = data.get("hits")
    if isinstance(hits, list):
        return [hit for hit in hits if isinstance(hit, dict)]
    files = data.get("files")
    if isinstance(files, list):
        return [item for item in files if isinstance(item, dict)]
    return []


def record_success(request_id: str, context: ToolContext, tool: str, metadata: dict[str, Any] | None = None) -> None:
    audit_store.record_event(request_id=request_id, context=context, tool=tool, status="succeeded", metadata=metadata)


def record_failure(request_id: str, context: ToolContext, tool: str, error: Exception) -> None:
    audit_store.record_event(request_id=request_id, context=context, tool=tool, status="failed", metadata={"error": str(error)})


async def run_tool(request_id: str, context: ToolContext, tool: str, call) -> Any:
    try:
        data = await call()
    except CapabilityClientError as exc:
        record_failure(request_id, context, tool, exc)
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except Exception as exc:
        record_failure(request_id, context, tool, exc)
        raise
    return data


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/openapi-dify.yaml", response_model=None)
def dify_openapi_spec() -> FileResponse:
    spec_path = Path(__file__).resolve().parents[1] / "openapi-dify.yaml"
    if not spec_path.exists():
        raise HTTPException(status_code=404, detail="openapi-dify.yaml not found")
    return FileResponse(spec_path, media_type="text/yaml")


@app.get("/v1/tools", dependencies=[Depends(require_auth)])
def list_tools() -> dict[str, list[ToolDescriptor]]:
    return {"tools": tool_descriptors()}


@app.post("/v1/session-key", response_model=ContextResponse, dependencies=[Depends(require_auth)])
def build_session_key(context: ToolContext) -> ContextResponse:
    return ContextResponse(
        session_key=context.session_key,
        user_key=context.user_key,
        chat_type=context.chat_type,
        shared_context=context.chat_type.value == "group" and not context.use_personal_context,
    )


@app.post("/v1/knowledge/search", response_model=ToolResponse, dependencies=[Depends(require_auth)])
async def search_enterprise_knowledge(request: SearchEnterpriseKnowledgeRequest) -> ToolResponse:
    request_id = new_request_id()
    data = await run_tool(request_id, request.context, "search_enterprise_knowledge", lambda: clients.search_enterprise_knowledge(request))
    sources = sources_from_search(data)
    record_success(request_id, request.context, "search_enterprise_knowledge", {"query": request.query, "result_count": len(sources)})
    return ToolResponse(
        request_id=request_id,
        session_key=request.context.session_key,
        tool="search_enterprise_knowledge",
        data=data,
        sources=sources,
    )


@app.post("/v1/knowledge/read", response_model=ToolResponse, dependencies=[Depends(require_auth)])
async def read_knowledge(request: ReadKnowledgeRequest) -> ToolResponse:
    request_id = new_request_id()
    data = await run_tool(request_id, request.context, "read_knowledge", lambda: clients.read_knowledge(request))
    record_success(request_id, request.context, "read_knowledge", {"document_id": request.document_id})
    return ToolResponse(
        request_id=request_id,
        session_key=request.context.session_key,
        tool="read_knowledge",
        data=data,
    )


@app.post("/v1/materials/search", response_model=ToolResponse, dependencies=[Depends(require_auth)])
async def search_materials(request: SearchMaterialsRequest) -> ToolResponse:
    request_id = new_request_id()
    data = await run_tool(request_id, request.context, "search_materials", lambda: clients.search_materials(request))
    sources = sources_from_search(data)
    record_success(request_id, request.context, "search_materials", {"query": request.query, "result_count": len(sources)})
    return ToolResponse(
        request_id=request_id,
        session_key=request.context.session_key,
        tool="search_materials",
        data=data,
        sources=sources,
    )


@app.post("/v1/materials/read", response_model=ToolResponse, dependencies=[Depends(require_auth)])
async def read_material(request: ReadMaterialRequest) -> ToolResponse:
    request_id = new_request_id()
    data = await run_tool(request_id, request.context, "read_material", lambda: clients.read_material(request))
    record_success(request_id, request.context, "read_material", {"relative_path": request.relative_path})
    return ToolResponse(
        request_id=request_id,
        session_key=request.context.session_key,
        tool="read_material",
        data=data,
    )


@app.post("/v1/copywriting/generate", response_model=ToolResponse, dependencies=[Depends(require_auth)])
async def generate_copywriting(request: GenerateCopywritingRequest) -> ToolResponse:
    request_id = new_request_id()
    data = await run_tool(request_id, request.context, "generate_copywriting", lambda: clients.generate_copywriting(request))
    record_success(request_id, request.context, "generate_copywriting", {"platform": request.platform, "has_extra_context": bool(request.extra_context)})
    return ToolResponse(
        request_id=request_id,
        session_key=request.context.session_key,
        tool="generate_copywriting",
        data=data,
    )


@app.post("/v1/artifacts/business", response_model=ToolResponse, dependencies=[Depends(require_auth)])
async def create_business_artifact(request: CreateBusinessArtifactRequest) -> ToolResponse:
    request_id = request.request_id or new_request_id()
    data = await run_tool(request_id, request.context, "create_business_artifact", lambda: clients.create_business_artifact(request))
    record_success(request_id, request.context, "create_business_artifact", {"artifact_type": request.artifact_type, "title": request.title})
    return ToolResponse(
        request_id=request_id,
        session_key=request.context.session_key,
        tool="create_business_artifact",
        data=data,
    )


@app.post("/v1/poster-jobs", response_model=ToolResponse, dependencies=[Depends(require_auth)])
async def create_poster_job(request: CreatePosterJobRequest) -> ToolResponse:
    request_id = request.request_id or new_request_id()
    data = await run_tool(request_id, request.context, "create_poster_job", lambda: clients.create_poster_job(request))
    record_success(request_id, request.context, "create_poster_job", {"job_id": data.get("job_id"), "status": data.get("status")})
    return ToolResponse(
        request_id=request_id,
        session_key=request.context.session_key,
        tool="create_poster_job",
        data=data,
    )


@app.get("/v1/poster-jobs/{job_id}", dependencies=[Depends(require_auth)])
async def get_poster_job(job_id: str) -> dict[str, Any]:
    return await clients.get_poster_job(job_id)


@app.post("/v1/artifacts/team", response_model=ToolResponse, dependencies=[Depends(require_auth)])
def create_team_artifact(request: CreateTeamArtifactRequest) -> ToolResponse:
    request_id = request.source_request_id or new_request_id()
    try:
        artifact = audit_store.create_artifact(request)
    except Exception as exc:
        record_failure(request_id, request.context, "create_team_artifact", exc)
        raise
    record_success(request_id, request.context, "create_team_artifact", {"artifact_id": artifact["artifact_id"], "visibility": request.visibility})
    return ToolResponse(
        request_id=request_id,
        session_key=request.context.session_key,
        tool="create_team_artifact",
        data=artifact,
    )


@app.post("/mcp", response_model=None)
async def mcp_endpoint(request: Request, _: None = Depends(require_auth)):
    payload = await request.json()
    if isinstance(payload, list):
        responses = []
        for item in payload:
            result = await handle_mcp_request(item, clients=clients, create_artifact=audit_store.create_artifact)
            if result is not None:
                responses.append(result)
        return responses
    result = await handle_mcp_request(payload, clients=clients, create_artifact=audit_store.create_artifact)
    if result is None:
        return Response(status_code=202)
    return result


@app.get("/v1/audit/events", dependencies=[Depends(require_auth)])
def list_audit_events(
    limit: int = Query(default=100, ge=1, le=500),
    session_key: str | None = None,
    tool: str | None = None,
) -> dict[str, Any]:
    return {"events": audit_store.list_events(limit=limit, session_key=session_key, tool=tool)}
