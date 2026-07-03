from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any

from fastapi.encoders import jsonable_encoder

from .catalog import MaterialCatalog
from .config import Settings
from .dify_metadata import DifyMetadataRepository, FileTextReader
from .external_tools import ExternalResearchTools

JSONRPC_VERSION = "2.0"
MCP_PROTOCOL_VERSION = "2025-06-18"


class MaterialMCPServer:
    """Minimal Streamable HTTP MCP endpoint for read-only material exploration tools."""

    def __init__(self, settings: Settings, catalog: MaterialCatalog, metadata_repo: DifyMetadataRepository) -> None:
        self.settings = settings
        self.catalog = catalog
        self.metadata_repo = metadata_repo
        self.file_reader = FileTextReader(settings.app_root)
        self.external_tools = ExternalResearchTools(settings)

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
                "read_document_chunks for factual answers; cite document_link_markdown, segment_position, and snippet. Do not claim access "
                "outside configured storage and Dify metadata. For image/logo requests, use search_files and return "
                "thumbnail_markdown_image when present, plus original_link_markdown for source verification. "
                "For PDF/PPT embedded images, use search_visual_assets. For person photo questions, use "
                "find_person_visual_candidates and label inferred results as candidates. "
                "For Markdown files, use read_file_text and preserve Markdown rendering. For MMB advisor use cases, "
                "combine internal material evidence with web_search, read_web_page, summarize_web_sources, and GitHub tools. "
                "Separate internal evidence, external sources, and model inference. External write actions are draft-only unless explicitly confirmed outside this server."
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
                "Search cataloged storage files by file name, relative path, or extension. Image upload results include thumbnail_markdown_image for fast display and original_link_markdown for verification.",
                {
                    "query": self._string("Optional filename or path search text."),
                    "extension": self._string("Optional extension, such as pdf or .docx."),
                    "limit": self._integer("Maximum files to return.", 1, 500, 50),
                },
            ),
            self._tool(
                "search_visual_assets",
                "Search PDF/PPT embedded visual_asset chunks and return signed /files/tools image links with source document context.",
                {
                    "query": self._string("Keywords such as 核心团队, 创始人照片, PPT 图, or PDF 图片."),
                    "dataset_id": self._string("Optional Dify dataset UUID."),
                    "document_id": self._string("Optional Dify document UUID."),
                    "section": self._string("Optional section title, such as 核心团队."),
                    "limit": self._integer("Maximum visual assets to return.", 1, 50, 10),
                },
            ),
            self._tool(
                "find_person_visual_candidates",
                "Find candidate PDF/PPT embedded images for a person by combining factual evidence with nearby visual_asset chunks.",
                {
                    "person_name": self._string("Person name, such as 陈立昌.", required=True),
                    "role_hint": self._string("Optional role hint, such as 创始人."),
                    "limit": self._integer("Maximum candidate visual assets to return.", 1, 20, 5),
                },
                required=["person_name"],
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
            self._tool(
                "web_search",
                "Search the public web through a configured provider such as Tavily, SerpAPI, or Brave Search. Returns external references, not MMB internal facts.",
                {
                    "query": self._string("Search query for market, industry, competitor, or current information.", required=True),
                    "provider": self._string("Optional provider override: tavily, serpapi, or brave."),
                    "limit": self._integer("Maximum results to return.", 1, 10, 5),
                },
                required=["query"],
            ),
            self._tool(
                "read_web_page",
                "Read a public web page as text with SSRF protections. Use after web_search before citing a source.",
                {
                    "url": self._string("Public http(s) URL to read.", required=True),
                    "max_chars": self._integer("Maximum characters to return.", 500, 50000, 12000),
                },
                required=["url"],
            ),
            self._tool(
                "summarize_web_sources",
                "Read and extract short excerpts from supplied URLs, or search then read top sources when query is provided.",
                {
                    "query": self._string("Optional query used when urls is empty."),
                    "urls": self._string("Optional comma/newline separated public URLs."),
                    "limit": self._integer("Maximum sources to read.", 1, 8, 3),
                    "max_chars_per_source": self._integer("Maximum characters per source excerpt.", 500, 8000, 2000),
                },
            ),
            self._tool(
                "github_search_repositories",
                "Search public GitHub repositories for open-source projects or implementation references.",
                {
                    "query": self._string("GitHub repository search query.", required=True),
                    "limit": self._integer("Maximum repositories to return.", 1, 10, 5),
                },
                required=["query"],
            ),
            self._tool(
                "github_search_code",
                "Search GitHub code. Public API may require GITHUB_TOKEN for code search.",
                {
                    "query": self._string("Code search query.", required=True),
                    "owner": self._string("Optional repository owner."),
                    "repo": self._string("Optional repository name."),
                    "limit": self._integer("Maximum code results to return.", 1, 10, 5),
                },
                required=["query"],
            ),
            self._tool(
                "github_read_file",
                "Read a file from a GitHub repository, such as README.md or configuration docs.",
                {
                    "owner": self._string("Repository owner.", required=True),
                    "repo": self._string("Repository name.", required=True),
                    "path": self._string("File path, such as README.md.", required=True),
                    "ref": self._string("Optional branch, tag, or commit SHA."),
                    "max_chars": self._integer("Maximum characters to return.", 500, 50000, 20000),
                },
                required=["owner", "repo", "path"],
            ),
            self._tool(
                "github_list_issues",
                "List GitHub issues for a repository. This is read-only.",
                {
                    "owner": self._string("Repository owner.", required=True),
                    "repo": self._string("Repository name.", required=True),
                    "state": self._string("Issue state: open, closed, or all."),
                    "limit": self._integer("Maximum issues to return.", 1, 20, 10),
                },
                required=["owner", "repo"],
            ),
            self._tool(
                "github_list_pull_requests",
                "List GitHub pull requests for a repository. This is read-only.",
                {
                    "owner": self._string("Repository owner.", required=True),
                    "repo": self._string("Repository name.", required=True),
                    "state": self._string("Pull request state: open, closed, or all."),
                    "limit": self._integer("Maximum pull requests to return.", 1, 20, 10),
                },
                required=["owner", "repo"],
            ),
            self._tool(
                "github_list_actions_runs",
                "List recent GitHub Actions workflow runs for a repository. This is read-only.",
                {
                    "owner": self._string("Repository owner.", required=True),
                    "repo": self._string("Repository name.", required=True),
                    "branch": self._string("Optional branch filter."),
                    "limit": self._integer("Maximum workflow runs to return.", 1, 20, 10),
                },
                required=["owner", "repo"],
            ),
            self._tool(
                "github_prepare_issue",
                "Prepare a GitHub issue draft. This tool does not write to GitHub and requires explicit confirmation before any real external action.",
                {
                    "owner": self._string("Repository owner.", required=True),
                    "repo": self._string("Repository name.", required=True),
                    "title": self._string("Issue title.", required=True),
                    "body": self._string("Issue body.", required=True),
                    "labels": self._string("Optional comma separated labels."),
                },
                required=["owner", "repo", "title", "body"],
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
            "search_visual_assets": self._search_visual_assets,
            "find_person_visual_candidates": self._find_person_visual_candidates,
            "read_file_text": self._read_file_text,
            "profile_materials": self._profile_materials,
            "list_material_changes": self._list_material_changes,
            "web_search": self._web_search,
            "read_web_page": self._read_web_page,
            "summarize_web_sources": self._summarize_web_sources,
            "github_search_repositories": self._github_search_repositories,
            "github_search_code": self._github_search_code,
            "github_read_file": self._github_read_file,
            "github_list_issues": self._github_list_issues,
            "github_list_pull_requests": self._github_list_pull_requests,
            "github_list_actions_runs": self._github_list_actions_runs,
            "github_prepare_issue": self._github_prepare_issue,
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
            "thumbnail_image_extensions": [".bmp", ".jpeg", ".jpg", ".png", ".webp"],
            "visual_assets": "search_visual_assets and find_person_visual_candidates expose PDF/PPT embedded images from visual_asset chunks with signed /files/tools links.",
            "rendering": "search_files returns thumbnail_markdown_image for Dify upload images; visual tools return image_markdown_images for PDF/PPT embedded images; read_file_text returns render_as=markdown for Markdown files.",
            "external_research": "web_search/read_web_page/summarize_web_sources expose external web references; GitHub tools expose public repository/code/issue/PR/Actions reads plus draft-only issue preparation.",
            "execution_policy": "External write actions are not executed by this server; draft tools require explicit confirmation before any separate write-capable integration is used.",
            "safety": "No delete, move, overwrite, ingest, reindex, secret-reading, public-posting, paid, or production-change tools are exposed.",
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

    def _search_visual_assets(self, arguments: dict[str, Any]) -> dict[str, Any]:
        assets = self.metadata_repo.search_visual_assets(
            query=arguments.get("query"),
            dataset_id=arguments.get("dataset_id"),
            document_id=arguments.get("document_id"),
            section=arguments.get("section"),
            limit=int(arguments.get("limit") or 10),
        )
        return {"query": arguments.get("query"), "assets": assets, "count": len(assets)}

    def _find_person_visual_candidates(self, arguments: dict[str, Any]) -> dict[str, Any]:
        person_name = str(arguments.get("person_name") or "").strip()
        if not person_name:
            raise ValueError("person_name is required")
        return self.metadata_repo.find_person_visual_candidates(
            person_name=person_name,
            role_hint=arguments.get("role_hint"),
            limit=int(arguments.get("limit") or 5),
        )

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

    def _web_search(self, arguments: dict[str, Any]) -> dict[str, Any]:
        return self.external_tools.web_search(
            query=str(arguments.get("query") or ""),
            provider=arguments.get("provider"),
            limit=int(arguments.get("limit") or 5),
        )

    def _read_web_page(self, arguments: dict[str, Any]) -> dict[str, Any]:
        return self.external_tools.read_web_page(
            url=str(arguments.get("url") or ""),
            max_chars=int(arguments.get("max_chars") or 12000),
        )

    def _summarize_web_sources(self, arguments: dict[str, Any]) -> dict[str, Any]:
        return self.external_tools.summarize_web_sources(
            query=arguments.get("query"),
            urls=arguments.get("urls"),
            limit=int(arguments.get("limit") or 3),
            max_chars_per_source=int(arguments.get("max_chars_per_source") or 2000),
        )

    def _github_search_repositories(self, arguments: dict[str, Any]) -> dict[str, Any]:
        return self.external_tools.github_search_repositories(
            query=str(arguments.get("query") or ""),
            limit=int(arguments.get("limit") or 5),
        )

    def _github_search_code(self, arguments: dict[str, Any]) -> dict[str, Any]:
        return self.external_tools.github_search_code(
            query=str(arguments.get("query") or ""),
            owner=arguments.get("owner"),
            repo=arguments.get("repo"),
            limit=int(arguments.get("limit") or 5),
        )

    def _github_read_file(self, arguments: dict[str, Any]) -> dict[str, Any]:
        return self.external_tools.github_read_file(
            owner=str(arguments.get("owner") or ""),
            repo=str(arguments.get("repo") or ""),
            path=str(arguments.get("path") or ""),
            ref=arguments.get("ref"),
            max_chars=int(arguments.get("max_chars") or 20000),
        )

    def _github_list_issues(self, arguments: dict[str, Any]) -> dict[str, Any]:
        return self.external_tools.github_list_issues(
            owner=str(arguments.get("owner") or ""),
            repo=str(arguments.get("repo") or ""),
            state=str(arguments.get("state") or "open"),
            limit=int(arguments.get("limit") or 10),
        )

    def _github_list_pull_requests(self, arguments: dict[str, Any]) -> dict[str, Any]:
        return self.external_tools.github_list_pull_requests(
            owner=str(arguments.get("owner") or ""),
            repo=str(arguments.get("repo") or ""),
            state=str(arguments.get("state") or "open"),
            limit=int(arguments.get("limit") or 10),
        )

    def _github_list_actions_runs(self, arguments: dict[str, Any]) -> dict[str, Any]:
        return self.external_tools.github_list_actions_runs(
            owner=str(arguments.get("owner") or ""),
            repo=str(arguments.get("repo") or ""),
            branch=arguments.get("branch"),
            limit=int(arguments.get("limit") or 10),
        )

    def _github_prepare_issue(self, arguments: dict[str, Any]) -> dict[str, Any]:
        return self.external_tools.github_prepare_issue(
            owner=str(arguments.get("owner") or ""),
            repo=str(arguments.get("repo") or ""),
            title=str(arguments.get("title") or ""),
            body=str(arguments.get("body") or ""),
            labels=arguments.get("labels"),
        )

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
