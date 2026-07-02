from __future__ import annotations

import base64
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx

from .config import Settings
from .prompting import should_use_default_bear
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
        mode = self.settings.image_mode.lower().strip()
        if mode == "responses":
            image_bytes = await self._generate_with_responses(request, prompt)
        elif mode == "images":
            image_bytes = await self._generate_with_images(prompt)
        else:
            raise ValueError(f"Unsupported POSTER_IMAGE_MODE: {self.settings.image_mode}")
        return ImageGenerationResult(image_bytes=image_bytes, prompt=prompt)

    def _api_url(self, path: str) -> str:
        base = self.settings.openai_base_url.rstrip("/")
        if base.endswith("/v1") and path.startswith("/v1/"):
            return base + path[3:]
        return base + path

    async def _generate_with_images(self, prompt: str) -> bytes:
        payload: dict[str, Any] = {
            "model": self.settings.image_model,
            "prompt": prompt,
            "size": self.settings.image_size,
            "n": 1,
        }
        data = await self._post_json(self._api_url("/v1/images/generations"), payload)
        item = data.get("data", [{}])[0]
        encoded = item.get("b64_json")
        if encoded:
            return base64.b64decode(encoded)
        url = item.get("url")
        if not url:
            raise RuntimeError("image response did not include b64_json or url")
        async with httpx.AsyncClient(timeout=self.settings.image_request_timeout) as client:
            response = await client.get(url)
            response.raise_for_status()
            return response.content

    async def _generate_with_responses(self, request: GeneratePosterRequest, prompt: str) -> bytes:
        input_value: str | list[dict[str, Any]] = prompt
        reference_image = self._default_bear_reference_data_url(request)
        if reference_image:
            input_value = [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "input_text",
                            "text": (
                                f"{prompt}\n\n"
                                "Attached image reference: use this MMB bear as the fixed character identity reference. "
                                "Keep the same orange plush body, rounded big eyes, black nose, light belly, friendly proportions, "
                                "and brand mascot feel. You may change pose, gesture, clothing accessories, and scene interaction "
                                "to match the poster theme, but the character should still clearly be the same MMB bear."
                            ),
                        },
                        {
                            "type": "input_image",
                            "image_url": reference_image,
                        },
                    ],
                }
            ]
        payload: dict[str, Any] = {
            "model": self.settings.llm_model,
            "input": input_value,
            "tools": [{"type": "image_generation"}],
        }
        data = await self._post_json(self._api_url("/v1/responses"), payload)
        encoded = self._find_image_base64(data)
        if encoded:
            return base64.b64decode(encoded.split(",", 1)[-1])
        raise RuntimeError("Responses output did not include image base64 result")

    def _find_image_base64(self, value: Any) -> str | None:
        if isinstance(value, dict):
            if value.get("type") == "image_generation_call" and isinstance(value.get("result"), str):
                return value["result"]
            for key in ("b64_json", "base64", "result", "data"):
                item = value.get(key)
                if isinstance(item, str) and self._looks_like_base64_image(item):
                    return item
            for item in value.values():
                found = self._find_image_base64(item)
                if found:
                    return found
        elif isinstance(value, list):
            for item in value:
                found = self._find_image_base64(item)
                if found:
                    return found
        return None

    @staticmethod
    def _looks_like_base64_image(value: str) -> bool:
        if value.startswith("data:image/"):
            return True
        return len(value) > 1000 and value[:16].startswith(("iVBOR", "/9j/", "R0lGOD"))

    def _default_bear_reference_data_url(self, request: GeneratePosterRequest) -> str | None:
        if not self.settings.default_bear_reference_enabled:
            return None
        if not should_use_default_bear(request):
            return None
        path = self.settings.default_bear_reference_path
        if not path.exists() or not path.is_file():
            return None
        mime_type = self._image_mime_type(path)
        encoded = base64.b64encode(path.read_bytes()).decode("ascii")
        return f"data:{mime_type};base64,{encoded}"

    @staticmethod
    def _image_mime_type(path: Path) -> str:
        suffix = path.suffix.lower()
        if suffix in {".jpg", ".jpeg"}:
            return "image/jpeg"
        if suffix == ".webp":
            return "image/webp"
        if suffix == ".gif":
            return "image/gif"
        return "image/png"

    async def _post_json(self, url: str, payload: dict[str, Any]) -> dict[str, Any]:
        headers = {
            "Authorization": f"Bearer {self.settings.openai_api_key}",
            "Content-Type": "application/json",
        }
        async with httpx.AsyncClient(timeout=self.settings.image_request_timeout) as client:
            response = await client.post(url, headers=headers, json=payload)
            if response.status_code >= 400:
                detail = response.text[:1000]
                raise RuntimeError(f"image request failed with HTTP {response.status_code}: {detail}")
            return response.json()
