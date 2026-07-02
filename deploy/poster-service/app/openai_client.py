from __future__ import annotations

import base64
from dataclasses import dataclass
from typing import Any

import httpx

from .config import Settings
from .schemas import GeneratePosterRequest


@dataclass(frozen=True)
class ImageGenerationResult:
    image_bytes: bytes
    prompt: str


class OpenAIImageClient:
    def __init__(self, settings: Settings):
        self.settings = settings

    async def generate(self, request: GeneratePosterRequest, prompt: str) -> ImageGenerationResult:
        if self.settings.allow_mock_openai:
            raise RuntimeError("mock-openai")
        if not self.settings.openai_api_key:
            raise ValueError("OPENAI_API_KEY is not configured")
        if self.settings.image_mode == "responses":
            image_bytes = await self._generate_with_responses(prompt)
        else:
            image_bytes = await self._generate_with_images(prompt)
        return ImageGenerationResult(image_bytes=image_bytes, prompt=prompt)

    async def _generate_with_images(self, prompt: str) -> bytes:
        payload: dict[str, Any] = {
            "model": self.settings.image_model,
            "prompt": prompt,
            "size": self.settings.image_size,
            "n": 1,
        }
        data = await self._post_json("https://api.openai.com/v1/images/generations", payload)
        item = data.get("data", [{}])[0]
        encoded = item.get("b64_json")
        if encoded:
            return base64.b64decode(encoded)
        url = item.get("url")
        if not url:
            raise RuntimeError("OpenAI image response did not include b64_json or url")
        async with httpx.AsyncClient(timeout=120) as client:
            response = await client.get(url)
            response.raise_for_status()
            return response.content

    async def _generate_with_responses(self, prompt: str) -> bytes:
        payload: dict[str, Any] = {
            "model": self.settings.llm_model,
            "input": prompt,
            "tools": [{"type": "image_generation"}],
        }
        data = await self._post_json("https://api.openai.com/v1/responses", payload)
        for item in data.get("output", []):
            if item.get("type") == "image_generation_call":
                encoded = item.get("result")
                if encoded:
                    return base64.b64decode(encoded)
        raise RuntimeError("OpenAI Responses output did not include an image_generation_call result")

    async def _post_json(self, url: str, payload: dict[str, Any]) -> dict[str, Any]:
        headers = {
            "Authorization": f"Bearer {self.settings.openai_api_key}",
            "Content-Type": "application/json",
        }
        async with httpx.AsyncClient(timeout=180) as client:
            response = await client.post(url, headers=headers, json=payload)
            if response.status_code >= 400:
                detail = response.text[:1000]
                raise RuntimeError(f"OpenAI request failed with HTTP {response.status_code}: {detail}")
            return response.json()
