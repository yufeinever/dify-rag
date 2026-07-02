from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any

from fastapi.encoders import jsonable_encoder

from .catalog import MaterialCatalog
from .config import Settings
from .dify_metadata import DifyMetadataRepository, FileTextReader

JSONRPC_VERSION = "2.0"
MCP_PROTOCOL_VERSION = "2025-06-18"


class MaterialMCPServer:
    """Minimal Streamable HTTP MCP endpoint for read-only material exploration tools."""

    def __init__(self, settings: Settings, catalog: MaterialCatalog, metadata_repo: DifyMetadataRepository) -> None:
        self.settings = settings
        self.catalog = catalog
        self.metadata_repo = metadata_repo
        self.file_reader = FileTextReader(settings.app_root)

    def handle(self, payload: dict[str, Any]) -> dict[str, Any]:
        request_id = payload.get("id")
        method = payload.get("method")
        try:
            if method == "initialize":
                return self._success(request_id, self.initialize())
            if method == "ping":
                return self._success(request_id, {})
            if method == "tools/list":
                return self._success(request_id, {"tools": self.tools()})
            if method == "tools/call":
                params = payload.get("params") or {}
                return self._success(request_id, self.call_tool(params.get("name"), params.get("arguments") or {}))
            return self._error(request_id, -32601, f"Method not found: {method}")
        except Exception as exc:
            return self._error(request_id, -32000, str(exc))

    def initialize(self) -> dict[str, Any]:
        return {
            "protocolVersion": MCP_PROTOCOL_VERSION,
            "capabilities": {"tools": {"listChanged": False}},
            "serverInfo": {"name": "material-catalog-mcp", "version": "0.2.0"},
            "instructions": (
                "Read-only tools for exploring the 150 Dify material store. Use search_segments and "
                "read_document_chunks for factual answers; cite document_name and snippet. Do not claim access "
                "outside configured storage and Dify metadata. For image/logo requests, use search_files and return "
                "markdown_image when present. For Markdown files, use read_file_text and preserve Markdown rendering."
            ),
        }

    def tools(self) -> list[dict[str, Any]]:
        return [
            self._tool(
                "server_info",
                "Inspect this material MCP server, its read-only boundary, and configured scan roots.",
                {},
            ),
            self._tool(
                "list_material_roots",
                "List allowed Dify material roots with file counts and sizes.",
                {"limit": self._integer("Unused compatibility limit.", 1, 1000)},
            ),
            self._tool(
                "list_datasets",
                "List Dify knowledge bases with document counts and word counts.",
                {"limit": self._integer("Maximum datasets to return.", 1, 200, 50)},
            ),
            self._tool(
                "list_documents",
                "List indexed Dify documents, optionally filtered by dataset or name query.",
                {
                    "dataset_id": self._string("Optional Dify dataset UUID."),
                    "query": self._string("Optional document-name search text."),
                    "limit": self._integer("Maximum documents to return.", 1, 500, 100),
                },
            ),
            self._tool(
                "search_segments",
                "Search indexed document segment content for evidence relevant to a question.",
                {
                    "query": self._string("Question or keywords to search for evidence.", required=True),
                    "dataset_id": self._string("Optional Dify dataset UUID."),
                    "document_id": self._string("Optional Dify document UUID."),
                    "limit": self._integer("Maximum evidence hits to return.", 1, 50, 10),
                },
                required=["query"],
            ),
            self._tool(
                "read_document_chunks",
                "Read indexed chunks from a document, optionally around a segment position.",
                {
                    "document_id": self._string("Dify document UUID.", required=True),
                    "center_position": self._integer("Optional segment position to expand around.", 0, 100000),
                    "before": self._integer("Chunks before center_position.", 0, 10, 2),
                    "after": self._integer("Chunks after center_position.", 0, 10, 2),
                    "limit": self._integer("Maximum chunks to return.", 1, 100, 20),
                },
                required=["document_id"],
            ),
            self._tool(
                "search_files",
                "Search cataloged storage files by file name, relative path, or extension. Image upload results include markdown_image for direct display.",
                {
                    "query": self._string("Optional filename or path search text."),
                    "extension": self._string("Optional extension, such as pdf or .docx."),
                    "limit": self._integer("Maximum files to return.", 1, 500, 50),
                },
            ),
            self._tool(
                "read_file_text",
                "Read safe text from a storage-relative file path. Markdown files return render_as=markdown; PDF/PPT should use indexed chunks first.",
                {
                    "relative_path": self._string("Path relative to /dify-app, e.g. storage/upload_files/...", required=True),
                    "max_chars": self._integer("Maximum characters to return.", 1, 50000, 12000),
                },
                required=["relative_path"],
            ),
            self._tool(
                "profile_materials",
                "Profile material assets by type, status, duplicates, and preprocessing recommendations.",
                {"limit": self._integer("Recent assets to include.", 1, 1000, 100)},
            ),
            self._tool(
                "list_material_changes",
                "List newly discovered, modified, or missing material files from the incremental catalog.",
                {"limit": self._integer("Maximum changes to return.", 1, 1000, 100)},
            ),
        ]

    def call_tool(self, name: str | None, arguments: dict[str, Any]) -> dict[str, Any]:
        handlers: dict[str, Callable[[dict[str, Any]], Any]] = {
            "server_info": self._server_info,
            "list_material_roots": self._list_material_roots,
            "list_datasets": self._list_datasets,
            "list_documents": self._list_documents,
            "search_segments": self._search_segments,
            "read_document_chunks": self._read_document_chunks,
            "search_files": self._search_files,
            "read_file_text": self._read_file_text,
            "profile_materials": self._profile_materials,
            "list_material_changes": self._list_material_changes,
        }
        if not name or name not in handlers:
            return self._tool_error("UNKNOWN_TOOL", f"Unknown tool: {name}")
        try:
            result = handlers[name](arguments)
        except Exception as exc:
            return self._tool_error("TOOL_ERROR", str(exc))
        encoded = jsonable_encoder(result)
        return {
            "content": [{"type": "text", "text": json.dumps(encoded, ensure_ascii=False, default=str)}],
            "structuredContent": encoded,
            "isError": False,
        }

    def _server_info(self, _: dict[str, Any]) -> dict[str, Any]:
        return {
            "name": "material-catalog-mcp",
            "version": "0.2.0",
            "read_only": True,
            "scan_roots": self.settings.scan_roots,
            "path_boundary": "All file paths are relative to the configured Dify app storage mount.",
            "supported_direct_text_extensions": [".txt", ".md", ".markdown", ".csv", ".json", ".yaml", ".yml", ".html", ".htm", ".xml", ".docx"],
            "renderable_image_extensions": [".bmp", ".gif", ".jpeg", ".jpg", ".png", ".svg", ".webp"],
            "rendering": "search_files returns markdown_image for Dify upload images; read_file_text returns render_as=markdown for Markdown files.",
            "safety": "No delete, move, overwrite, ingest, reindex, or secret-reading tools are exposed.",
        }

    def _list_material_roots(self, _: dict[str, Any]) -> dict[str, Any]:
        roots = self.catalog.roots_summary(self.settings.scan_roots)
        return {
            "roots": [
                {key: value for key, value in root.items() if key != "path"}
                for root in roots
            ]
        }

    def _list_datasets(self, arguments: dict[str, Any]) -> dict[str, Any]:
        return {"datasets": self.metadata_repo.list_datasets(limit=int(arguments.get("limit") or 50))}

    def _list_documents(self, arguments: dict[str, Any]) -> dict[str, Any]:
        return {
            "documents": self.metadata_repo.list_documents(
                dataset_id=arguments.get("dataset_id"),
                query=arguments.get("query"),
                limit=int(arguments.get("limit") or 100),
            )
        }

    def _search_segments(self, arguments: dict[str, Any]) -> dict[str, Any]:
        query = str(arguments.get("query") or "").strip()
        if not query:
            raise ValueError("query is required")
        hits = self.metadata_repo.search_segments(
            query=query,
            dataset_id=arguments.get("dataset_id"),
            document_id=arguments.get("document_id"),
            limit=int(arguments.get("limit") or 10),
        )
        return {"query": query, "hits": hits, "count": len(hits)}

    def _read_document_chunks(self, arguments: dict[str, Any]) -> dict[str, Any]:
        document_id = str(arguments.get("document_id") or "").strip()
        if not document_id:
            raise ValueError("document_id is required")
        center = arguments.get("center_position")
        return self.metadata_repo.read_document_chunks(
            document_id=document_id,
            center_position=int(center) if center is not None else None,
            before=int(arguments.get("before") or 2),
            after=int(arguments.get("after") or 2),
            limit=int(arguments.get("limit") or 20),
        )

    def _search_files(self, arguments: dict[str, Any]) -> dict[str, Any]:
        catalog_result = self.catalog.search_files(
            query=arguments.get("query"),
            extension=arguments.get("extension"),
            limit=int(arguments.get("limit") or 50),
        )
        upload_files = self.metadata_repo.search_upload_files(
            query=arguments.get("query"),
            extension=arguments.get("extension"),
            limit=int(arguments.get("limit") or 50),
        )
        catalog_files = [self._decorate_catalog_file(self._sanitize_asset(row)) for row in catalog_result.get("files", [])]
        return {
            "upload_files": upload_files,
            "catalog_files": catalog_files,
            "count": len(upload_files) + len(catalog_files),
        }

    def _decorate_catalog_file(self, row: dict[str, Any]) -> dict[str, Any]:
        extension = str(row.get("extension") or "").lower()
        if extension in {".bmp", ".gif", ".jpeg", ".jpg", ".png", ".svg", ".webp"}:
            row["file_kind"] = "image"
            row["is_renderable_image"] = False
            row["display_hint"] = "该结果来自 storage 目录扫描，缺少 Dify upload_file_id，不能直接生成 /files/... 预览图；优先使用同名 upload_files 结果中的 markdown_image。"
        elif extension in {".md", ".markdown"}:
            row["file_kind"] = "markdown"
            row["is_markdown"] = True
            row["display_hint"] = "需要展示内容时，调用 read_file_text 并按 render_as=markdown 渲染。"
        return row

    def _read_file_text(self, arguments: dict[str, Any]) -> dict[str, Any]:
        relative_path = str(arguments.get("relative_path") or "").strip()
        if not relative_path:
            raise ValueError("relative_path is required")
        return self.file_reader.read_file_text(relative_path, max_chars=int(arguments.get("max_chars") or 12000))

    def _profile_materials(self, arguments: dict[str, Any]) -> dict[str, Any]:
        return self._sanitize_catalog_payload(self.catalog.profile(limit=int(arguments.get("limit") or 100)))

    def _list_material_changes(self, arguments: dict[str, Any]) -> dict[str, Any]:
        return self._sanitize_catalog_payload(self.catalog.changes(limit=int(arguments.get("limit") or 100)))

    def _sanitize_catalog_payload(self, value: Any) -> Any:
        if isinstance(value, dict):
            return {key: self._sanitize_catalog_payload(item) for key, item in value.items() if key not in {"path", "sha256", "fingerprint"}}
        if isinstance(value, list):
            return [self._sanitize_catalog_payload(item) for item in value]
        return value

    def _sanitize_asset(self, row: dict[str, Any]) -> dict[str, Any]:
        return {
            key: self._sanitize_catalog_payload(value)
            for key, value in row.items()
            if key not in {"path", "sha256", "fingerprint"}
        }

    def _tool(self, name: str, description: str, properties: dict[str, Any], required: list[str] | None = None) -> dict[str, Any]:
        required_fields = required or [key for key, schema in properties.items() if schema.get("required_marker", False)]
        return {
            "name": name,
            "title": name,
            "description": description,
            "inputSchema": {
                "type": "object",
                "properties": {key: self._clean_schema(value) for key, value in properties.items()},
                "required": required_fields,
                "additionalProperties": False,
            },
            "outputSchema": {"type": "object", "additionalProperties": True},
            "annotations": {"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True},
        }

    def _string(self, description: str, required: bool = False) -> dict[str, Any]:
        return {"type": "string", "description": description, "required_marker": required}

    def _integer(self, description: str, minimum: int, maximum: int, default: int | None = None) -> dict[str, Any]:
        schema: dict[str, Any] = {"type": "integer", "description": description, "minimum": minimum, "maximum": maximum}
        if default is not None:
            schema["default"] = default
        return schema

    def _clean_schema(self, schema: dict[str, Any]) -> dict[str, Any]:
        cleaned = dict(schema)
        cleaned.pop("required_marker", None)
        return cleaned

    def _tool_error(self, code: str, message: str) -> dict[str, Any]:
        payload = {"ok": False, "error": {"code": code, "message": message, "retryable": False}}
        return {
            "content": [{"type": "text", "text": json.dumps(payload, ensure_ascii=False)}],
            "structuredContent": payload,
            "isError": True,
        }

    def _success(self, request_id: Any, result: dict[str, Any]) -> dict[str, Any]:
        return {"jsonrpc": JSONRPC_VERSION, "id": request_id, "result": jsonable_encoder(result)}

    def _error(self, request_id: Any, code: int, message: str) -> dict[str, Any]:
        return {"jsonrpc": JSONRPC_VERSION, "id": request_id, "error": {"code": code, "message": message}}
