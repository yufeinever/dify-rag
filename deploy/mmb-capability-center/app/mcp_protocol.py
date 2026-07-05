from __future__ import annotations

import inspect
import json
import uuid
from collections.abc import Awaitable, Callable
from typing import Any

from pydantic import ValidationError

from .clients import CapabilityClientError, ServiceClients
from .models import (
    ChatType,
    CreateBusinessArtifactRequest,
    CreatePosterJobRequest,
    CreateTeamArtifactRequest,
    ReadKnowledgeRequest,
    ReadMaterialRequest,
    ResourceScope,
    SearchEnterpriseKnowledgeRequest,
    SearchMaterialsRequest,
    ToolContext,
)


MCP_PROTOCOL_VERSION = "2025-06-18"


def _schema(properties: dict[str, Any], required: list[str] | None = None) -> dict[str, Any]:
    return {
        "type": "object",
        "properties": properties,
        "required": required or [],
        "additionalProperties": False,
    }


CONTEXT_PROPERTIES: dict[str, Any] = {
    "tenant_id": {"type": "string", "description": "Workspace or tenant id.", "default": "mmb"},
    "bot_id": {"type": "string", "description": "Agent/profile id.", "default": "hermes-mmb-agent"},
    "channel": {"type": "string", "default": "hermes"},
    "chat_type": {"type": "string", "enum": ["p2p", "group"], "default": "p2p"},
    "open_id": {"type": "string", "description": "User id for p2p context."},
    "sender_open_id": {"type": "string", "description": "Sender id in group context."},
    "chat_id": {"type": "string", "description": "Group/session id."},
    "department_id": {"type": "string"},
    "project_id": {"type": "string"},
    "role": {"type": "string", "default": "member"},
    "use_personal_context": {"type": "boolean", "default": False},
}


TOOLS: list[dict[str, Any]] = [
    {
        "name": "search_knowledge",
        "title": "Search MMB knowledge",
        "description": "Search approved MMB enterprise, department, or project knowledge before answering factual internal questions.",
        "inputSchema": _schema(
            {
                **CONTEXT_PROPERTIES,
                "query": {"type": "string", "description": "Search query."},
                "dataset_id": {"type": "string"},
                "document_id": {"type": "string"},
                "limit": {"type": "integer", "minimum": 1, "maximum": 30, "default": 8},
            },
            ["query"],
        ),
        "annotations": {"readOnlyHint": True},
    },
    {
        "name": "read_knowledge",
        "title": "Read MMB knowledge document",
        "description": "Read nearby chunks from a known MMB knowledge document after search_knowledge returns a document id.",
        "inputSchema": _schema(
            {
                **CONTEXT_PROPERTIES,
                "document_id": {"type": "string"},
                "center_position": {"type": "integer"},
                "before": {"type": "integer", "minimum": 0, "maximum": 10, "default": 2},
                "after": {"type": "integer", "minimum": 0, "maximum": 10, "default": 2},
                "limit": {"type": "integer", "minimum": 1, "maximum": 100, "default": 20},
            },
            ["document_id"],
        ),
        "annotations": {"readOnlyHint": True},
    },
    {
        "name": "search_materials",
        "title": "Search MMB materials",
        "description": "Find MMB source materials, images, files, visual assets, and asset records.",
        "inputSchema": _schema(
            {
                **CONTEXT_PROPERTIES,
                "query": {"type": "string"},
                "extension": {"type": "string", "description": "Optional file extension filter, for example pdf, docx, png."},
                "limit": {"type": "integer", "minimum": 1, "maximum": 100, "default": 20},
            }
        ),
        "annotations": {"readOnlyHint": True},
    },
    {
        "name": "read_material",
        "title": "Read MMB material file",
        "description": "Read text from a known material file path returned by search_materials.",
        "inputSchema": _schema(
            {
                **CONTEXT_PROPERTIES,
                "relative_path": {"type": "string"},
                "max_chars": {"type": "integer", "minimum": 1, "maximum": 50000, "default": 12000},
            },
            ["relative_path"],
        ),
        "annotations": {"readOnlyHint": True},
    },
    {
        "name": "create_artifact",
        "title": "Create MMB business artifact",
        "description": "Create or request a real MMB Word, Excel, PPT, or structured business artifact from prepared content.",
        "inputSchema": _schema(
            {
                **CONTEXT_PROPERTIES,
                "artifact_type": {
                    "type": "string",
                    "enum": ["word", "excel", "ppt", "document", "spreadsheet", "presentation", "team_note", "other"],
                    "default": "other",
                },
                "title": {"type": "string"},
                "content": {"type": "string"},
                "instructions": {"type": "string"},
                "metadata": {"type": "object", "additionalProperties": True},
                "request_id": {"type": "string"},
            },
            ["title", "content"],
        ),
        "annotations": {"readOnlyHint": False, "destructiveHint": False},
    },
    {
        "name": "create_poster_job",
        "title": "Create MMB poster job",
        "description": "Create an asynchronous MMB poster generation job after the poster brief is clear. Return a job_id for tracking and downstream polling/delivery; this tool does not upload images to Feishu or any other channel directly.",
        "inputSchema": _schema(
            {
                **CONTEXT_PROPERTIES,
                "user_query": {"type": "string"},
                "theme": {"type": "string"},
                "audience": {"type": "string"},
                "main_title": {"type": "string"},
                "subtitle": {"type": "string"},
                "selling_points": {"type": "array", "items": {"type": "string"}},
                "size": {"type": "string", "default": "1080x1440"},
                "request_id": {"type": "string"},
            },
            ["user_query"],
        ),
        "annotations": {"readOnlyHint": False, "destructiveHint": False},
    },
    {
        "name": "save_team_asset",
        "title": "Save MMB team asset",
        "description": "Save a confirmed output as a team, project, or personal asset. Use only after the user confirms saving.",
        "inputSchema": _schema(
            {
                **CONTEXT_PROPERTIES,
                "artifact_type": {"type": "string", "enum": ["copywriting", "poster", "summary", "research", "other"], "default": "other"},
                "title": {"type": "string"},
                "content": {"type": "string"},
                "visibility": {"type": "string", "enum": ["team", "project", "personal"], "default": "team"},
                "source_request_id": {"type": "string"},
                "metadata": {"type": "object", "additionalProperties": True},
            },
            ["title", "content"],
        ),
        "annotations": {"readOnlyHint": False, "destructiveHint": False},
    },
]


def _request_id() -> str:
    return str(uuid.uuid4())


def _context(args: dict[str, Any]) -> ToolContext:
    chat_type = args.get("chat_type") or ("group" if args.get("chat_id") else "p2p")
    open_id = args.get("open_id") or args.get("sender_open_id") or args.get("user_id") or args.get("session_id") or "hermes-user"
    return ToolContext(
        tenant_id=args.get("tenant_id") or "mmb",
        bot_id=args.get("bot_id") or "hermes-mmb-agent",
        channel=args.get("channel") or "hermes",
        chat_type=ChatType(chat_type),
        open_id=open_id if chat_type == "p2p" else args.get("open_id"),
        sender_open_id=args.get("sender_open_id") or open_id,
        chat_id=args.get("chat_id") or args.get("session_id"),
        department_id=args.get("department_id"),
        project_id=args.get("project_id"),
        role=args.get("role") or "member",
        scopes=[ResourceScope.ENTERPRISE],
        use_personal_context=bool(args.get("use_personal_context", False)),
    )


def _clean_args(arguments: dict[str, Any] | None) -> dict[str, Any]:
    return {key: value for key, value in (arguments or {}).items() if value is not None}


def _mcp_result(request_id: Any, result: dict[str, Any]) -> dict[str, Any]:
    text = json.dumps(result, ensure_ascii=False, default=str)
    return {
        "jsonrpc": "2.0",
        "id": request_id,
        "result": {
            "content": [{"type": "text", "text": text}],
            "structuredContent": result,
            "isError": False,
        },
    }


def _mcp_error(request_id: Any, code: int, message: str, details: dict[str, Any] | None = None) -> dict[str, Any]:
    return {
        "jsonrpc": "2.0",
        "id": request_id,
        "error": {
            "code": code,
            "message": message,
            "data": details or {},
        },
    }


async def _maybe_await(value: Any) -> Any:
    if inspect.isawaitable(value):
        return await value
    return value


async def call_mcp_tool(
    name: str,
    arguments: dict[str, Any] | None,
    *,
    clients: ServiceClients,
    create_artifact: Callable[[CreateTeamArtifactRequest], dict[str, Any]],
    register_poster_delivery: Callable[[ToolContext, dict[str, Any]], Any] | None = None,
) -> dict[str, Any]:
    args = _clean_args(arguments)
    context = _context(args)
    if name == "search_knowledge":
        return await clients.search_enterprise_knowledge(
            SearchEnterpriseKnowledgeRequest(
                context=context,
                query=args["query"],
                dataset_id=args.get("dataset_id"),
                document_id=args.get("document_id"),
                limit=args.get("limit", 8),
            )
        )
    if name == "read_knowledge":
        return await clients.read_knowledge(
            ReadKnowledgeRequest(
                context=context,
                document_id=args["document_id"],
                center_position=args.get("center_position"),
                before=args.get("before", 2),
                after=args.get("after", 2),
                limit=args.get("limit", 20),
            )
        )
    if name == "search_materials":
        return await clients.search_materials(
            SearchMaterialsRequest(context=context, query=args.get("query"), extension=args.get("extension"), limit=args.get("limit", 20))
        )
    if name == "read_material":
        return await clients.read_material(
            ReadMaterialRequest(context=context, relative_path=args["relative_path"], max_chars=args.get("max_chars", 12000))
        )
    if name == "create_artifact":
        return await clients.create_business_artifact(
            CreateBusinessArtifactRequest(
                context=context,
                artifact_type=args.get("artifact_type", "other"),
                title=args["title"],
                content=args["content"],
                instructions=args.get("instructions"),
                metadata=args.get("metadata") or {},
                request_id=args.get("request_id"),
            )
        )
    if name == "create_poster_job":
        brief = None
        if args.get("theme") or args.get("main_title") or args.get("audience"):
            from .models import PosterBrief

            brief = PosterBrief(
                theme=args.get("theme") or args["user_query"],
                audience=args.get("audience"),
                main_title=args.get("main_title"),
                subtitle=args.get("subtitle"),
                selling_points=args.get("selling_points") or [],
                brand_constraints="参考 MMB 品牌资料和现有素材；不要生成不可证实的价格、承诺或水印。",
            )
        result = await clients.create_poster_job(
            CreatePosterJobRequest(
                context=context,
                user_query=args["user_query"],
                brief=brief,
                size=args.get("size", "1080x1440"),
                request_id=args.get("request_id"),
            )
        )
        if register_poster_delivery is not None:
            await _maybe_await(register_poster_delivery(context, result))
        return result
    if name == "save_team_asset":
        return await _maybe_await(
            create_artifact(
                CreateTeamArtifactRequest(
                    context=context,
                    artifact_type=args.get("artifact_type", "other"),
                    title=args["title"],
                    content=args["content"],
                    visibility=args.get("visibility", "team"),
                    source_request_id=args.get("source_request_id"),
                    metadata=args.get("metadata") or {},
                )
            )
        )
    raise KeyError(name)


async def handle_mcp_request(
    payload: dict[str, Any],
    *,
    clients: ServiceClients,
    create_artifact: Callable[[CreateTeamArtifactRequest], dict[str, Any]],
    register_poster_delivery: Callable[[ToolContext, dict[str, Any]], Any] | None = None,
) -> dict[str, Any] | None:
    method = payload.get("method")
    request_id = payload.get("id")

    if method == "initialize":
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "result": {
                "protocolVersion": MCP_PROTOCOL_VERSION,
                "capabilities": {"tools": {"listChanged": False}},
                "serverInfo": {"name": "mmb-capability-center", "version": "0.2.0"},
            },
        }
    if method == "notifications/initialized":
        return None
    if method == "tools/list":
        return {"jsonrpc": "2.0", "id": request_id, "result": {"tools": TOOLS}}
    if method == "tools/call":
        params = payload.get("params") or {}
        tool_name = params.get("name")
        if not tool_name:
            return _mcp_error(request_id, -32602, "tools/call requires params.name")
        try:
            result = await call_mcp_tool(
                tool_name,
                params.get("arguments") or {},
                clients=clients,
                create_artifact=create_artifact,
                register_poster_delivery=register_poster_delivery,
            )
            return _mcp_result(request_id, {"ok": True, "tool": tool_name, "data": result})
        except KeyError:
            return _mcp_error(request_id, -32601, f"Unknown tool: {tool_name}")
        except (ValidationError, ValueError) as exc:
            return _mcp_error(request_id, -32602, str(exc))
        except CapabilityClientError as exc:
            return _mcp_result(request_id, {"ok": False, "tool": tool_name, "error": str(exc)})
        except Exception as exc:
            return _mcp_result(request_id, {"ok": False, "tool": tool_name, "error": str(exc)})

    return _mcp_error(request_id, -32601, f"Unsupported MCP method: {method}")
