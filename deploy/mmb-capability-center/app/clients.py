from __future__ import annotations

import json
import re
import uuid
from typing import Any
from urllib.parse import parse_qsl, unquote, urlencode, urlsplit, urlunsplit

import httpx

from .config import Settings
from .models import (
    CreatePosterJobRequest,
    CreateBusinessArtifactRequest,
    GenerateCopywritingRequest,
    PosterBrief,
    ToolContext,
    ReadKnowledgeRequest,
    ReadMaterialRequest,
    SearchEnterpriseKnowledgeRequest,
    SearchMaterialsRequest,
)


class CapabilityClientError(RuntimeError):
    pass


_TOOL_FILE_URL_RE = re.compile(r"(?P<url>(?:https?://[^\s)\]<>\"']+|/files/tools/[^\s)\]<>\"']+))")


def _base_url(value: object) -> str:
    return str(value).rstrip("/")


def _json_without_none(value: Any) -> Any:
    if hasattr(value, "model_dump"):
        return value.model_dump(exclude_none=True)
    if isinstance(value, list):
        return [_json_without_none(item) for item in value]
    if isinstance(value, dict):
        return {key: _json_without_none(item) for key, item in value.items() if item is not None}
    return value


def answer_from_dify(payload: dict[str, Any]) -> str:
    answer = payload.get("answer")
    if isinstance(answer, str) and answer.strip():
        return answer

    data = payload.get("data")
    if isinstance(data, dict):
        outputs = data.get("outputs")
        if isinstance(outputs, dict):
            for key in ("answer", "text", "output"):
                value = outputs.get(key)
                if isinstance(value, str) and value.strip():
                    return value

    text = payload.get("text")
    if isinstance(text, str) and text.strip():
        return text
    return str(payload)



_ARTIFACT_EXTENSIONS: dict[str, set[str]] = {
    "poster": {"png", "jpg", "jpeg", "webp"},
    "image": {"png", "jpg", "jpeg", "webp"},
    "pptx": {"ppt", "pptx"},
    "visual_ppt": {"ppt", "pptx"},
    "word": {"doc", "docx"},
    "document": {"doc", "docx"},
    "excel": {"xls", "xlsx", "csv"},
    "spreadsheet": {"xls", "xlsx", "csv"},
    "pdf": {"pdf"},
    "file": set(),
}

_MIME_BY_EXTENSION: dict[str, str] = {
    "pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    "ppt": "application/vnd.ms-powerpoint",
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "doc": "application/msword",
    "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "xls": "application/vnd.ms-excel",
    "csv": "text/csv",
    "pdf": "application/pdf",
    "png": "image/png",
    "jpg": "image/jpeg",
    "jpeg": "image/jpeg",
    "webp": "image/webp",
}


def _extension_from_url(url: str) -> str:
    path = urlsplit(url).path
    name = unquote(path.rsplit("/", 1)[-1])
    if "." not in name:
        return ""
    return name.rsplit(".", 1)[-1].lower()


def _filename_from_url(url: str, default_filename: str | None) -> str:
    path = urlsplit(url).path
    name = unquote(path.rsplit("/", 1)[-1])
    if name:
        return name
    return default_filename or "artifact.bin"


def _mime_from_filename(filename: str, fallback: str | None = None) -> str:
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    return fallback or _MIME_BY_EXTENSION.get(ext, "application/octet-stream")


def _dify_file_base_url(settings: Settings) -> str:
    parts = urlsplit(str(settings.dify_base_url))
    path = parts.path.rstrip("/")
    if path.endswith("/v1"):
        path = path[:-3] or ""
    return urlunsplit((parts.scheme, parts.netloc, path, "", "")).rstrip("/")


def _absolute_file_url(url: str, settings: Settings) -> str:
    url = _tool_file_attachment_url(url)
    if url.startswith("http://") or url.startswith("https://"):
        return url
    if url.startswith("/"):
        return f"{_dify_file_base_url(settings)}{url}"
    return url


def _artifact_allowed(url: str, artifact_type: str) -> bool:
    allowed = _ARTIFACT_EXTENSIONS.get(artifact_type, set())
    if not allowed:
        return True
    return _extension_from_url(url) in allowed


def _iter_file_url_strings(value: Any):
    if isinstance(value, str):
        for match in _TOOL_FILE_URL_RE.finditer(value):
            yield match.group("url")
        return
    if isinstance(value, list):
        for item in value:
            yield from _iter_file_url_strings(item)
        return
    if isinstance(value, dict):
        for key in ("url", "file_url", "download_url", "signed_url"):
            item = value.get(key)
            if isinstance(item, str):
                yield item
        for item in value.values():
            yield from _iter_file_url_strings(item)


def extract_generated_artifacts(payload: dict[str, Any], *, artifact_type: str, default_filename: str | None, settings: Settings) -> list[dict[str, Any]]:
    artifacts: list[dict[str, Any]] = []
    seen: set[str] = set()
    for raw_url in _iter_file_url_strings(payload):
        absolute_url = _absolute_file_url(raw_url, settings)
        if absolute_url in seen or not _artifact_allowed(absolute_url, artifact_type):
            continue
        seen.add(absolute_url)
        filename = _filename_from_url(absolute_url, default_filename)
        artifacts.append({"artifact_type": artifact_type, "filename": filename, "mime_type": _mime_from_filename(filename), "file_url": absolute_url})
    return artifacts


def attach_artifact_delivery_metadata(payload: dict[str, Any], *, artifact_type: str, default_filename: str | None, settings: Settings) -> dict[str, Any]:
    result = dict(payload)
    artifacts = extract_generated_artifacts(result, artifact_type=artifact_type, default_filename=default_filename, settings=settings)
    if artifacts:
        result["generated_artifacts"] = artifacts
        result["delivery_registered"] = False
        result["delivery_status"] = "pending_registration"
        return result
    if result.get("status") not in {"not_configured", "not_supported"}:
        result["status"] = "blocked_missing_file"
        result["delivery_registered"] = False
        result["delivery_status"] = "blocked_missing_file"
        result["message"] = "生成工具没有返回可下载文件地址，已阻止声称文件完成；请检查对应 Dify 助手是否返回真实附件。"
    return result

def _tool_file_attachment_url(url: str) -> str:
    if "/files/tools/" not in url:
        return url
    parts = urlsplit(url)
    query = dict(parse_qsl(parts.query, keep_blank_values=True))
    if query.get("as_attachment") == "true":
        return url
    query["as_attachment"] = "true"
    return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(query), parts.fragment))


def _attach_tool_file_downloads(value: Any) -> Any:
    if isinstance(value, str):
        return _TOOL_FILE_URL_RE.sub(lambda match: _tool_file_attachment_url(match.group("url")), value)
    if isinstance(value, list):
        return [_attach_tool_file_downloads(item) for item in value]
    if isinstance(value, dict):
        return {key: _attach_tool_file_downloads(item) for key, item in value.items()}
    return value


class ServiceClients:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    async def _request_json(self, method: str, url: str, **kwargs: Any) -> dict[str, Any]:
        timeout = httpx.Timeout(self.settings.http_timeout_seconds)
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.request(method, url, **kwargs)
        if response.status_code >= 400:
            raise CapabilityClientError(f"{method} {url} failed: {response.status_code} {response.text}")
        try:
            data = response.json()
        except ValueError as exc:
            raise CapabilityClientError(f"{method} {url} returned non-json response") from exc
        if not isinstance(data, dict):
            raise CapabilityClientError(f"{method} {url} returned unexpected response")
        return data

    async def search_enterprise_knowledge(self, request: SearchEnterpriseKnowledgeRequest) -> dict[str, Any]:
        params: dict[str, Any] = {
            "query": request.query,
            "limit": request.limit,
        }
        if request.dataset_id:
            params["dataset_id"] = request.dataset_id
        if request.document_id:
            params["document_id"] = request.document_id
        return await self._request_json(
            "GET",
            f"{_base_url(self.settings.material_catalog_url)}/v1/segments/search",
            params=params,
        )

    async def read_knowledge(self, request: ReadKnowledgeRequest) -> dict[str, Any]:
        params: dict[str, Any] = {
            "before": request.before,
            "after": request.after,
            "limit": request.limit,
        }
        if request.center_position is not None:
            params["center_position"] = request.center_position
        return await self._request_json(
            "GET",
            f"{_base_url(self.settings.material_catalog_url)}/v1/documents/{request.document_id}/chunks",
            params=params,
        )

    async def search_materials(self, request: SearchMaterialsRequest) -> dict[str, Any]:
        params: dict[str, Any] = {"limit": request.limit}
        if request.query:
            params["query"] = request.query
        if request.extension:
            params["extension"] = request.extension
        return await self._request_json(
            "GET",
            f"{_base_url(self.settings.material_catalog_url)}/v1/materials/files",
            params=params,
        )

    async def read_material(self, request: ReadMaterialRequest) -> dict[str, Any]:
        return await self._request_json(
            "GET",
            f"{_base_url(self.settings.material_catalog_url)}/v1/materials/file-text",
            params={"relative_path": request.relative_path, "max_chars": request.max_chars},
        )

    async def _chat_app(self, *, api_key: str, query: str, user: str, session_key: str, inputs: dict[str, Any] | None = None) -> dict[str, Any]:
        payload = {
            "inputs": {**(inputs or {}), "session_key": session_key},
            "query": query,
            "user": user,
            "response_mode": "blocking",
        }
        try:
            data = await self._request_json(
                "POST",
                f"{_base_url(self.settings.dify_base_url)}/chat-messages",
                headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                json=payload,
            )
        except CapabilityClientError as exc:
            if "Agent Chat App does not support blocking mode" not in str(exc):
                raise
            return await self._chat_app_streaming(
                api_key=api_key,
                query=query,
                user=user,
                session_key=session_key,
                inputs=inputs,
            )
        return {
            "status": "requested",
            "answer": _attach_tool_file_downloads(answer_from_dify(data)),
            "raw": data,
        }

    async def _chat_app_streaming(
        self,
        *,
        api_key: str,
        query: str,
        user: str,
        session_key: str,
        inputs: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        payload = {
            "inputs": {**(inputs or {}), "session_key": session_key},
            "query": query,
            "user": user,
            "response_mode": "streaming",
        }
        url = f"{_base_url(self.settings.dify_base_url)}/chat-messages"
        headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
        answer_parts: list[str] = []
        files: list[dict[str, Any]] = []
        raw_events: list[dict[str, Any]] = []

        timeout = httpx.Timeout(self.settings.http_timeout_seconds)
        async with httpx.AsyncClient(timeout=timeout) as client:
            async with client.stream("POST", url, headers=headers, json=payload) as response:
                if response.status_code >= 400:
                    body = (await response.aread()).decode("utf-8", errors="replace")
                    raise CapabilityClientError(f"POST {url} failed: {response.status_code} {body}")
                async for line in response.aiter_lines():
                    line = line.strip()
                    if not line or not line.startswith("data:"):
                        continue
                    event_payload = line.removeprefix("data:").strip()
                    if event_payload == "[DONE]":
                        continue
                    try:
                        event = json.loads(event_payload)
                    except ValueError:
                        continue
                    if not isinstance(event, dict):
                        continue
                    raw_events.append(event)
                    answer = event.get("answer")
                    if isinstance(answer, str) and answer:
                        answer_parts.append(answer)
                    if event.get("event") == "message_file":
                        files.append(event)
                    event_files = event.get("files")
                    if isinstance(event_files, list):
                        files.extend(item for item in event_files if isinstance(item, dict))

        answer = _attach_tool_file_downloads("".join(answer_parts).strip())
        return {
            "status": "requested",
            "answer": answer or "Dify streaming request completed without text answer. Check files/raw_events for generated assets.",
            "files": _attach_tool_file_downloads(files),
            "raw_events": raw_events[-30:],
        }

    async def answer_mmb_question(self, *, context: ToolContext, question: str, extra_context: str | None = None) -> dict[str, Any]:
        api_key = self.settings.dify_default_app_api_key
        if not api_key:
            return {
                "status": "not_configured",
                "message": "DIFY_DEFAULT_APP_API_KEY is not configured; answer directly with GPT-5.5 using retrieved MMB context.",
                "question": question,
            }
        query_parts = ["请作为 MMB 企业业务助手回答用户问题。", f"用户问题：{question}"]
        if extra_context:
            query_parts.append(f"补充上下文：{extra_context}")
        return await self._chat_app(
            api_key=api_key,
            query="\n".join(query_parts),
            user=context.user_key,
            session_key=context.session_key,
            inputs={"extra_context": extra_context or ""},
        )

    async def generate_copywriting(self, request: GenerateCopywritingRequest) -> dict[str, Any]:
        api_key = self.settings.dify_copywriting_app_api_key or self.settings.dify_default_app_api_key
        if not api_key:
            return {
                "status": "not_configured",
                "message": "DIFY_COPYWRITING_APP_API_KEY or DIFY_DEFAULT_APP_API_KEY is not configured; draft copy directly with GPT-5.5 and retrieved MMB context.",
                "user_query": request.user_query,
            }

        query_parts = ["请生成可直接使用的 MMB 文案。", f"用户需求：{request.user_query}"]
        if request.platform:
            query_parts.append(f"发布平台：{request.platform}")
        if request.audience:
            query_parts.append(f"目标人群：{request.audience}")
        if request.style:
            query_parts.append(f"风格：{request.style}")
        if request.extra_context:
            query_parts.append(f"补充资料：{request.extra_context}")

        return await self._chat_app(
            api_key=api_key,
            query="\n".join(query_parts),
            user=request.context.user_key,
            session_key=request.context.session_key,
            inputs={
                "platform": request.platform or "",
                "audience": request.audience or "",
                "style": request.style or "",
                "extra_context": request.extra_context or "",
            },
        )

    async def create_poster_job(self, request: CreatePosterJobRequest) -> dict[str, Any]:
        brief = request.brief or PosterBrief(
            theme=request.user_query,
            background=request.user_query,
            audience="企业内部协作场景",
            brand_constraints="参考 MMB 品牌资料和现有素材；不要生成不可证实的价格、承诺或水印。",
        )
        request_id = request.request_id or str(uuid.uuid4())
        payload = {
            "brief": _json_without_none(brief),
            "assets": _json_without_none(request.assets),
            "size": request.size,
            "overlay_text": False,
            "request_id": request_id,
            "user_query": request.user_query,
        }
        return await self._request_json(
            "POST",
            f"{_base_url(self.settings.poster_service_url)}/v1/poster-jobs",
            json=payload,
        )

    async def create_visual_ppt(
        self,
        *,
        context: ToolContext,
        title: str,
        outline: str,
        slides_json: str | None = None,
        filename: str | None = None,
        slide_count: int | None = None,
        style_preset: str | None = None,
    ) -> dict[str, Any]:
        api_key = self.settings.dify_visual_ppt_app_api_key
        if not api_key:
            return {
                "status": "not_configured",
                "message": "DIFY_VISUAL_PPT_APP_API_KEY is not configured; no real visual PPT file was created.",
                "artifact_type": "visual_ppt",
                "title": title,
            }
        query_parts = [
            "请调用 MMB视觉PPT助手的 create_visual_ppt_deck 能力生成真实 .pptx 附件，不要只返回文字大纲。",
            f"标题：{title}",
            f"大纲：{outline}",
        ]
        if slides_json:
            query_parts.append(f"Slides JSON：{slides_json}")
        if filename:
            query_parts.append(f"文件名：{filename}")
        if slide_count:
            query_parts.append(f"目标页数：{slide_count}")
        if style_preset:
            query_parts.append(f"视觉风格：{style_preset}")
        result = await self._chat_app_streaming(
            api_key=api_key,
            query="\n".join(query_parts),
            user=context.user_key,
            session_key=context.session_key,
            inputs={
                "title": title,
                "outline": outline,
                "slides_json": slides_json or "",
                "filename": filename or "",
                "slide_count": str(slide_count or ""),
                "style_preset": style_preset or "",
            },
        )
        return attach_artifact_delivery_metadata(
            result,
            artifact_type="pptx",
            default_filename=filename or f"{title}.pptx",
            settings=self.settings,
        )

    async def create_business_artifact(self, request: CreateBusinessArtifactRequest) -> dict[str, Any]:
        if request.artifact_type in {"ppt", "presentation"}:
            return {
                "status": "not_supported",
                "message": "create_office_file is limited to Word and Excel. Use create_visual_ppt for PPT generation.",
                "artifact_type": request.artifact_type,
                "title": request.title,
            }
        api_key = self.settings.dify_office_app_api_key or self.settings.dify_business_artifact_app_api_key or self.settings.dify_default_app_api_key
        if not api_key:
            return {
                "status": "not_configured",
                "message": "DIFY_OFFICE_APP_API_KEY, DIFY_BUSINESS_ARTIFACT_APP_API_KEY, or DIFY_DEFAULT_APP_API_KEY is not configured; no real Word/Excel file was created.",
                "artifact_type": request.artifact_type,
                "title": request.title,
                "content": request.content,
                "metadata": request.metadata,
            }

        query = "\n".join(
            [
                "请根据以下内容生成真实 Word 或 Excel 附件。",
                f"产物类型：{request.artifact_type}",
                f"标题：{request.title}",
                f"内容：{request.content}",
                f"补充要求：{request.instructions or '无'}",
                "请直接调用可用的 office_artifact_tools/create_office_artifact 生成附件，不要只返回文字说明。PPT 不在本工具范围内。",
            ]
        )
        result = await self._chat_app(
            api_key=api_key,
            query=query,
            user=request.context.user_key,
            session_key=request.context.session_key,
            inputs={
                "artifact_type": request.artifact_type,
                "title": request.title,
                "instructions": request.instructions or "",
            },
        )
        delivery_type = "word" if request.artifact_type in {"word", "document"} else "excel"
        default_extension = "docx" if delivery_type == "word" else "xlsx"
        default_filename = str(request.metadata.get("filename") or f"{request.title}.{default_extension}")
        return attach_artifact_delivery_metadata(
            result,
            artifact_type=delivery_type,
            default_filename=default_filename,
            settings=self.settings,
        )

    async def get_poster_job(self, job_id: str) -> dict[str, Any]:
        return await self._request_json(
            "GET",
            f"{_base_url(self.settings.poster_service_url)}/v1/poster-jobs/{job_id}",
        )
