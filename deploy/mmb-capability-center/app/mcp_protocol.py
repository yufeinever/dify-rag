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
    GenerateCopywritingRequest,
    PosterBrief,
    ReadKnowledgeRequest,
    ReadMaterialRequest,
    ResourceScope,
    SearchEnterpriseKnowledgeRequest,
    SearchMaterialsRequest,
    ToolContext,
)


MCP_PROTOCOL_VERSION = "2025-06-18"


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


LEGACY_TOOL_ALIASES: dict[str, str] = {
    "search_knowledge": "search_mmb_context",
    "search_materials": "search_mmb_materials",
    "create_artifact": "create_office_file",
    "create_poster_job": "create_poster",
    "generate_copywriting": "create_campaign_copy",
}


OFFICE_TYPE_ALIASES: dict[str, str] = {
    "document": "word",
    "docx": "word",
    "word": "word",
    "spreadsheet": "excel",
    "xlsx": "excel",
    "excel": "excel",
    "ppt": "ppt",
    "pptx": "ppt",
    "powerpoint": "ppt",
    "slides": "presentation",
    "presentation": "presentation",
}


def _schema(properties: dict[str, Any], required: list[str] | None = None) -> dict[str, Any]:
    return {
        "type": "object",
        "properties": properties,
        "required": required or [],
        "additionalProperties": False,
    }


def _object_schema(properties: dict[str, Any] | None = None) -> dict[str, Any]:
    return {"type": "object", "properties": properties or {}, "additionalProperties": True}


TOOLS: list[dict[str, Any]] = [
    {
        "name": "search_mmb_context",
        "title": "Search MMB enterprise context",
        "description": (
            "Use this tool before answering factual questions about MMB internal knowledge, brand facts, product plans, "
            "financing material, policies, cases, training content, or indexed company documents. Do not use it for public "
            "real-time facts unless the user is combining public facts with MMB private context. Return source-aware evidence; "
            "if the result is thin, answer with uncertainty or ask a short clarification instead of inventing facts."
        ),
        "inputSchema": _schema(
            {
                **CONTEXT_PROPERTIES,
                "query": {"type": "string", "description": "Natural-language MMB internal question or evidence query."},
                "dataset_id": {"type": "string", "description": "Optional Dify dataset UUID when a specific knowledge base is required."},
                "document_id": {"type": "string", "description": "Optional document UUID to restrict evidence search."},
                "limit": {"type": "integer", "minimum": 1, "maximum": 30, "default": 8},
            },
            ["query"],
        ),
        "outputSchema": _object_schema({"hits": {"type": "array", "items": {"type": "object", "additionalProperties": True}}}),
        "annotations": {"readOnlyHint": True, "destructiveHint": False},
    },
    {
        "name": "search_mmb_materials",
        "title": "Search MMB materials and visual assets",
        "description": (
            "Use this tool when the user asks to find source files, images, logos, brand assets, PPT/PDF/Word files, "
            "historical campaign references, store photos, founder/team photos, or visual assets. Do not use it for normal "
            "business Q&A unless the user needs actual files or asset candidates. Prefer concrete keywords and extension filters."
        ),
        "inputSchema": _schema(
            {
                **CONTEXT_PROPERTIES,
                "query": {"type": "string", "description": "Optional filename, person, topic, visual asset, or material keyword."},
                "extension": {"type": "string", "description": "Optional extension filter such as png, jpg, pdf, pptx, docx."},
                "limit": {"type": "integer", "minimum": 1, "maximum": 100, "default": 20},
            }
        ),
        "outputSchema": _object_schema({"files": {"type": "array", "items": {"type": "object", "additionalProperties": True}}}),
        "annotations": {"readOnlyHint": True, "destructiveHint": False},
    },
    {
        "name": "answer_mmb_question",
        "title": "Answer MMB business question",
        "description": (
            "Use this high-level workflow only for complex MMB business explanations, strategy advice, structured analysis, "
            "or decisions that need an MMB app/workflow rather than simple retrieval. For one-off factual questions, call "
            "search_mmb_context first. If no Dify business app key is configured, this tool returns not_configured; then answer "
            "directly with GPT-5.5 using retrieved evidence instead of pretending the workflow ran."
        ),
        "inputSchema": _schema(
            {
                **CONTEXT_PROPERTIES,
                "question": {"type": "string", "description": "The user's complete MMB business question."},
                "extra_context": {"type": "string", "description": "Optional retrieved evidence or conversation context."},
            },
            ["question"],
        ),
        "outputSchema": _object_schema({"status": {"type": "string"}, "answer": {"type": "string"}}),
        "annotations": {"readOnlyHint": False, "destructiveHint": False},
    },
    {
        "name": "create_campaign_copy",
        "title": "Create MMB campaign copy",
        "description": (
            "Use this tool when the user explicitly asks for reusable MMB marketing copy such as WeChat Moments, Xiaohongshu, "
            "community posts, sales scripts, customer messages, or campaign announcements. Do not use it for posters, Office files, "
            "or pure factual Q&A. If a dedicated copywriting Dify app is not configured, return not_configured so the agent can draft "
            "directly with GPT-5.5 and retrieved MMB context."
        ),
        "inputSchema": _schema(
            {
                **CONTEXT_PROPERTIES,
                "user_query": {"type": "string", "description": "The user's copywriting request."},
                "platform": {"type": "string", "description": "Optional platform such as WeChat Moments, Xiaohongshu, group, sales."},
                "audience": {"type": "string", "description": "Optional target audience."},
                "style": {"type": "string", "description": "Optional tone or style."},
                "extra_context": {"type": "string", "description": "Optional retrieved MMB evidence or material notes."},
            },
            ["user_query"],
        ),
        "outputSchema": _object_schema({"status": {"type": "string"}, "answer": {"type": "string"}}),
        "annotations": {"readOnlyHint": False, "destructiveHint": False},
    },
    {
        "name": "create_poster",
        "title": "Create MMB poster",
        "description": (
            "Use this workflow tool when the user asks to create, generate, design, or produce a real MMB poster, campaign image, "
            "share image, event visual, or promotional graphic. Do not use it for text-only copywriting, strategy plans, or ordinary "
            "image search. Before calling, extract theme, audience, title, subtitle, selling points, size, and useful material references; "
            "ask one short clarification only if the core theme is missing. This creates an asynchronous poster job and registers Feishu "
            "background delivery when chat context is available. Return the job_id as a tracking id and never claim the final image is ready "
            "until status is succeeded with poster_url."
        ),
        "inputSchema": _schema(
            {
                **CONTEXT_PROPERTIES,
                "user_query": {"type": "string", "description": "Original user poster request."},
                "theme": {"type": "string", "description": "Poster theme or campaign topic."},
                "audience": {"type": "string", "description": "Target audience."},
                "main_title": {"type": "string", "description": "Main visible title if the user supplied one."},
                "subtitle": {"type": "string", "description": "Optional subtitle."},
                "selling_points": {"type": "array", "items": {"type": "string"}, "description": "Short selling points or visual messages."},
                "size": {"type": "string", "default": "1080x1440", "description": "Poster size, default vertical social poster."},
                "request_id": {"type": "string", "description": "Optional idempotency/request id."},
            },
            ["user_query"],
        ),
        "outputSchema": _object_schema({"job_id": {"type": "string"}, "status": {"type": "string"}}),
        "annotations": {"readOnlyHint": False, "destructiveHint": False},
    },
    {
        "name": "create_visual_ppt",
        "title": "Create MMB visual PowerPoint deck",
        "description": (
            "Use this workflow tool for all PPT generation requests, especially beautiful, visual, image-first PPT, pitch decks, "
            "financing roadshows, presentations, report decks, and slide decks where the expected output is a real .pptx attachment. "
            "Do not answer with text only. Prepare a clear outline or slides_json first. This routes to MMB视觉PPT助手 when configured; "
            "otherwise it returns not_configured instead of using terminal fallback. If delivery_registered is true, stop and tell the user the file will be sent automatically; do not use terminal fallback."
        ),
        "inputSchema": _schema(
            {
                **CONTEXT_PROPERTIES,
                "title": {"type": "string", "description": "Deck title."},
                "outline": {"type": "string", "description": "Markdown outline with slide titles and short visual bullets."},
                "slides_json": {"type": "string", "description": "Optional JSON array of slide objects for precise slide control."},
                "filename": {"type": "string", "description": "Optional output filename ending with .pptx."},
                "slide_count": {"type": "integer", "minimum": 1, "maximum": 12, "default": 6},
                "style_preset": {"type": "string", "description": "Optional visual style preset such as mmb_modern_pitch or finance_pitch."},
                "request_id": {"type": "string"},
            },
            ["title"],
        ),
        "outputSchema": _object_schema({"status": {"type": "string"}, "file_url": {"type": "string"}}),
        "annotations": {"readOnlyHint": False, "destructiveHint": False},
    },
    {
        "name": "create_office_file",
        "title": "Create MMB Word or Excel file",
        "description": (
            "Use this workflow tool only when the user asks for a real Word document or Excel spreadsheet: proposal, report, plan, "
            "meeting minutes, schedule, budget table, checklist, workbook, or spreadsheet. Do not use it for PPT, slides, decks, "
            "roadshows, or presentations; every PPT request must use create_visual_ppt. Do not use it when the user only wants chat text. "
            "Provide stable content, artifact_type, title, and any format instructions. "
            "If delivery_registered is true, stop and tell the user the file will be sent automatically; do not use terminal fallback. If the backend Office/Dify artifact app is not configured, return not_configured and do not claim a file was created."
        ),
        "inputSchema": _schema(
            {
                **CONTEXT_PROPERTIES,
                "artifact_type": {"type": "string", "enum": ["word", "excel", "document", "spreadsheet"], "default": "word"},
                "title": {"type": "string", "description": "File title."},
                "content": {"type": "string", "description": "Markdown body, document content, table content, or spreadsheet data. Never pass PPT slide outlines here."},
                "instructions": {"type": "string", "description": "Optional Word/Excel formatting, audience, tone, delivery, or file requirements."},
                "filename": {"type": "string", "description": "Optional requested filename."},
                "request_id": {"type": "string"},
            },
            ["title", "content"],
        ),
        "outputSchema": _object_schema({"status": {"type": "string"}, "file_url": {"type": "string"}}),
        "annotations": {"readOnlyHint": False, "destructiveHint": False},
    },
    {
        "name": "send_feishu_asset",
        "title": "Send existing asset to Feishu",
        "description": (
            "Use this delivery-layer tool only after a real image/file/job already exists and the user asks to send it to Feishu or the "
            "current Feishu chat should receive the finished asset. It does not generate business content. First version supports registering "
            "poster jobs, existing image URLs, and existing file URLs for Feishu background delivery. It registers delivery only; it does not generate business content."
        ),
        "inputSchema": _schema(
            {
                **CONTEXT_PROPERTIES,
                "asset_type": {"type": "string", "enum": ["poster_job", "image", "file"], "default": "poster_job"},
                "job_id": {"type": "string", "description": "Existing poster job id to register for Feishu delivery."},
                "asset_url": {"type": "string", "description": "Existing image/file URL when supported by delivery backend."},
                "title": {"type": "string", "description": "Optional asset title."},
                "session_id": {"type": "string", "description": "Optional Hermes session id for target resolution."},
            }
        ),
        "outputSchema": _object_schema({"status": {"type": "string"}, "message": {"type": "string"}}),
        "annotations": {"readOnlyHint": False, "destructiveHint": False},
    },
    {
        "name": "save_team_asset",
        "title": "Save MMB team asset",
        "description": (
            "Save a confirmed output as a team, project, or personal asset. Use only after the user explicitly asks to save, archive, "
            "沉淀, 归档, or continue the result later. Do not use it for private drafts or intermediate reasoning without confirmation."
        ),
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
        "outputSchema": _object_schema({"artifact_id": {"type": "string"}}),
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


def _office_type(value: str | None) -> str:
    return OFFICE_TYPE_ALIASES.get((value or "word").lower(), "other")


def _poster_brief(args: dict[str, Any]) -> PosterBrief | None:
    if not (args.get("theme") or args.get("main_title") or args.get("audience") or args.get("subtitle") or args.get("selling_points")):
        return None
    return PosterBrief(
        theme=args.get("theme") or args["user_query"],
        audience=args.get("audience"),
        main_title=args.get("main_title"),
        subtitle=args.get("subtitle"),
        selling_points=args.get("selling_points") or [],
        brand_constraints="参考 MMB 品牌资料和现有素材；不要生成不可证实的价格、承诺或水印。",
    )


async def call_mcp_tool(
    name: str,
    arguments: dict[str, Any] | None,
    *,
    clients: ServiceClients,
    create_artifact: Callable[[CreateTeamArtifactRequest], dict[str, Any]],
    register_poster_delivery: Callable[[ToolContext, dict[str, Any]], Any] | None = None,
    register_artifact_delivery: Callable[..., Any] | None = None,
) -> dict[str, Any]:
    args = _clean_args(arguments)
    context = _context(args)
    tool_name = LEGACY_TOOL_ALIASES.get(name, name)

    if tool_name == "search_mmb_context":
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
    if tool_name == "search_mmb_materials":
        return await clients.search_materials(
            SearchMaterialsRequest(context=context, query=args.get("query"), extension=args.get("extension"), limit=args.get("limit", 20))
        )
    if name == "read_material":
        return await clients.read_material(
            ReadMaterialRequest(context=context, relative_path=args["relative_path"], max_chars=args.get("max_chars", 12000))
        )
    if tool_name == "answer_mmb_question":
        return await clients.answer_mmb_question(
            context=context,
            question=args["question"],
            extra_context=args.get("extra_context"),
        )
    if tool_name == "create_campaign_copy":
        return await clients.generate_copywriting(
            GenerateCopywritingRequest(
                context=context,
                user_query=args["user_query"],
                platform=args.get("platform"),
                audience=args.get("audience"),
                style=args.get("style"),
                extra_context=args.get("extra_context"),
            )
        )
    if tool_name == "create_poster":
        result = await clients.create_poster_job(
            CreatePosterJobRequest(
                context=context,
                user_query=args["user_query"],
                brief=_poster_brief(args),
                size=args.get("size", "1080x1440"),
                request_id=args.get("request_id"),
            )
        )
        if register_poster_delivery is not None:
            await _maybe_await(register_poster_delivery(context, result))
        return result
    if tool_name == "create_visual_ppt":
        result = await clients.create_visual_ppt(
            context=context,
            title=args["title"],
            outline=args.get("outline") or args["title"],
            slides_json=args.get("slides_json"),
            filename=args.get("filename"),
            slide_count=args.get("slide_count"),
            style_preset=args.get("style_preset"),
        )
        if register_artifact_delivery is not None:
            await _maybe_await(register_artifact_delivery(context, result, artifact_type="pptx", default_filename=args.get("filename") or f"{args['title']}.pptx"))
        return result
    if tool_name == "create_office_file":
        metadata = {"capability": "create_office_file"}
        if args.get("filename"):
            metadata["filename"] = args.get("filename")
        result = await clients.create_business_artifact(
            CreateBusinessArtifactRequest(
                context=context,
                artifact_type=_office_type(args.get("artifact_type")),
                title=args["title"],
                content=args["content"],
                instructions=args.get("instructions"),
                metadata=metadata,
                request_id=args.get("request_id"),
            )
        )
        if register_artifact_delivery is not None:
            delivery_type = "word" if _office_type(args.get("artifact_type")) == "word" else "excel"
            default_ext = "docx" if delivery_type == "word" else "xlsx"
            await _maybe_await(register_artifact_delivery(context, result, artifact_type=delivery_type, default_filename=args.get("filename") or f"{args['title']}.{default_ext}"))
        return result
    if tool_name == "send_feishu_asset":
        asset_type = args.get("asset_type") or "poster_job"
        job_id = args.get("job_id")
        if asset_type == "poster_job" and job_id and register_poster_delivery is not None:
            delivery_data = {
                "job_id": job_id,
                "status": "registered_for_delivery",
                "poster_url": args.get("asset_url"),
                "title": args.get("title"),
            }
            await _maybe_await(register_poster_delivery(context, delivery_data))
            return {
                "status": "registered_for_delivery",
                "message": "已登记飞书后台回传；海报任务完成后会发送到当前飞书会话。",
                "job_id": job_id,
                "delivery_registered": True,
            }
        asset_url = args.get("asset_url")
        if asset_type in {"image", "file"} and isinstance(asset_url, str) and asset_url and register_artifact_delivery is not None:
            delivery_type = "image" if asset_type == "image" else "file"
            delivery_data = {
                "status": "registered_for_delivery",
                "generated_artifacts": [
                    {
                        "artifact_type": delivery_type,
                        "filename": args.get("title") or ("image.png" if delivery_type == "image" else "artifact.bin"),
                        "file_url": asset_url,
                    }
                ],
            }
            await _maybe_await(register_artifact_delivery(context, delivery_data, artifact_type=delivery_type, default_filename=args.get("title")))
            return {
                "status": "registered_for_delivery",
                "message": "已登记飞书后台回传；文件会发送到当前飞书会话。",
                "asset_type": asset_type,
                "delivery_registered": True,
                "artifact_deliveries": delivery_data.get("artifact_deliveries", []),
            }
        return {
            "status": "not_configured",
            "message": "send_feishu_asset 需要 poster_job + job_id，或 image/file + asset_url，并且服务端需启用投递后端。",
            "asset_type": asset_type,
        }
    if tool_name == "save_team_asset":
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
    register_artifact_delivery: Callable[..., Any] | None = None,
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
                "serverInfo": {"name": "mmb-capability-center", "version": "0.3.0"},
                "instructions": (
                    "MMB Capability Center exposes high-level business workflow tools. Dify workflows, plugins, knowledge bases, "
                    "and Feishu delivery are implementation layers behind these tools. Prefer workflow tools for standard enterprise "
                    "deliverables and retrieval tools only for evidence/material exploration."
                ),
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
                register_artifact_delivery=register_artifact_delivery,
            )
            return _mcp_result(request_id, {"ok": True, "tool": LEGACY_TOOL_ALIASES.get(tool_name, tool_name), "requested_tool": tool_name, "data": result})
        except KeyError:
            return _mcp_error(request_id, -32601, f"Unknown tool: {tool_name}")
        except (ValidationError, ValueError) as exc:
            return _mcp_error(request_id, -32602, str(exc))
        except CapabilityClientError as exc:
            return _mcp_result(request_id, {"ok": False, "tool": LEGACY_TOOL_ALIASES.get(tool_name, tool_name), "requested_tool": tool_name, "error": str(exc)})
        except Exception as exc:
            return _mcp_result(request_id, {"ok": False, "tool": LEGACY_TOOL_ALIASES.get(tool_name, tool_name), "requested_tool": tool_name, "error": str(exc)})

    return _mcp_error(request_id, -32601, f"Unsupported MCP method: {method}")
