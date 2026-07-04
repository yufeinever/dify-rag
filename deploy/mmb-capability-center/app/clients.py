from __future__ import annotations

import uuid
from typing import Any

import httpx

from .config import Settings
from .models import (
    CreatePosterJobRequest,
    GenerateCopywritingRequest,
    PosterBrief,
    SearchEnterpriseKnowledgeRequest,
    SearchMaterialsRequest,
)


class CapabilityClientError(RuntimeError):
    pass


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

    async def generate_copywriting(self, request: GenerateCopywritingRequest) -> dict[str, Any]:
        api_key = self.settings.dify_copywriting_app_api_key or self.settings.dify_default_app_api_key
        if not api_key:
            raise CapabilityClientError("DIFY_COPYWRITING_APP_API_KEY or DIFY_DEFAULT_APP_API_KEY is required")

        query_parts = ["请生成可直接使用的 MMB 文案。", f"用户需求：{request.user_query}"]
        if request.platform:
            query_parts.append(f"发布平台：{request.platform}")
        if request.audience:
            query_parts.append(f"目标人群：{request.audience}")
        if request.style:
            query_parts.append(f"风格：{request.style}")
        if request.extra_context:
            query_parts.append(f"补充资料：{request.extra_context}")

        payload = {
            "inputs": {
                "platform": request.platform or "",
                "audience": request.audience or "",
                "style": request.style or "",
                "extra_context": request.extra_context or "",
                "session_key": request.context.session_key,
            },
            "query": "\n".join(query_parts),
            "user": request.context.user_key,
            "response_mode": "blocking",
        }
        data = await self._request_json(
            "POST",
            f"{_base_url(self.settings.dify_base_url)}/chat-messages",
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json=payload,
        )
        return {
            "answer": answer_from_dify(data),
            "raw": data,
        }

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

    async def get_poster_job(self, job_id: str) -> dict[str, Any]:
        return await self._request_json(
            "GET",
            f"{_base_url(self.settings.poster_service_url)}/v1/poster-jobs/{job_id}",
        )
