from __future__ import annotations

import base64
import binascii
import io
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urljoin

import httpx
from PIL import Image, UnidentifiedImageError

from .config import Settings
from .prompting import should_use_default_bear
from .schemas import GeneratePosterRequest


@dataclass(frozen=True)
class ImageGenerationResult:
    image_bytes: bytes
    prompt: str
    reference_image_stats: dict[str, int]


class OpenAIImageClient:
    def __init__(self, settings: Settings):
        self.settings = settings

    async def generate(
        self, request: GeneratePosterRequest, prompt: str
    ) -> ImageGenerationResult:
        if self.settings.allow_mock_openai:
            raise RuntimeError("mock-openai")
        if not self.settings.openai_api_key:
            raise ValueError("OPENAI_API_KEY is not configured")
        mode = self.settings.image_mode.lower().strip()
        if mode == "responses":
            image_bytes, reference_image_stats = await self._generate_with_responses(
                request, prompt
            )
        elif mode == "images":
            if request.assets:
                raise ValueError(
                    "POSTER_IMAGE_MODE=images does not support reference images; use responses mode"
                )
            image_bytes = await self._generate_with_images(prompt)
            reference_image_stats = self._reference_stats(
                request, loaded=0, default_bear=0
            )
        else:
            raise ValueError(
                f"Unsupported POSTER_IMAGE_MODE: {self.settings.image_mode}"
            )
        return ImageGenerationResult(
            image_bytes=image_bytes,
            prompt=prompt,
            reference_image_stats=reference_image_stats,
        )

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
        async with httpx.AsyncClient(
            timeout=self.settings.image_request_timeout
        ) as client:
            response = await client.get(url)
            response.raise_for_status()
            return response.content

    async def _generate_with_responses(
        self, request: GeneratePosterRequest, prompt: str
    ) -> tuple[bytes, dict[str, int]]:
        references, stats = await self._prepare_reference_images(request)
        content: list[dict[str, Any]] = [
            {"type": "input_text", "text": self._reference_instructions(prompt, stats)}
        ]
        content.extend(
            {"type": "input_image", "image_url": image_url}
            for _, image_url in references
        )
        input_value: list[dict[str, Any]] = [{"role": "user", "content": content}]
        payload: dict[str, Any] = {
            "model": self.settings.llm_model,
            "input": input_value,
            "tools": [{"type": "image_generation"}],
        }
        data = await self._post_json(self._api_url("/v1/responses"), payload)
        encoded = self._find_image_base64(data)
        if encoded:
            return base64.b64decode(encoded.split(",", 1)[-1]), stats
        raise RuntimeError("Responses output did not include image base64 result")

    async def _prepare_reference_images(
        self, request: GeneratePosterRequest
    ) -> tuple[list[tuple[str, str]], dict[str, int]]:
        limits = {"character": 3, "scene": 3, "other": 5}
        ordered_assets = sorted(
            enumerate(request.assets),
            key=lambda item: (
                {"character": 0, "scene": 1, "other": 2}[self._asset_kind(item[1])],
                item[0],
            ),
        )
        counts = {kind: 0 for kind in limits}
        references: list[tuple[str, str]] = []
        default_bear = 0
        for _, asset in ordered_assets:
            kind = self._asset_kind(asset)
            if asset.source == "default_mmb_bear":
                image_url = self._built_in_bear_data_url()
                if not image_url:
                    raise ValueError("built-in MMB bear reference image is unavailable")
                counts["character"] += 1
                references.append(("character", image_url))
                default_bear = 1
                continue
            if kind == "other" and not asset.source:
                # Legacy knowledge assets were prompt-only metadata. New visual assets always declare a source.
                continue
            is_generated_character = (
                kind == "character" and asset.source == "generated_character"
            )
            if is_generated_character and counts.get("generated_character", 0) >= 1:
                raise ValueError("only one generated character reference is allowed")
            counts[kind] += 0 if is_generated_character else 1
            if is_generated_character:
                counts["generated_character"] = 1
            if counts[kind] > limits[kind]:
                raise ValueError(
                    f"too many {kind} reference images; maximum is {limits[kind]}"
                )
            if not asset.url or not asset.url.strip():
                raise ValueError(f"{kind} reference image is missing a URL")
            references.append(
                (kind, await self._load_reference_image(asset.url.strip()))
            )

        if counts["character"] == 0:
            image_url = self._default_bear_reference_data_url(request)
            if image_url:
                references.insert(0, ("character", image_url))
                default_bear = 1
        return references, self._reference_stats(
            request, loaded=len(references), default_bear=default_bear
        )

    async def _load_reference_image(self, url: str) -> str:
        if url.startswith("data:image/"):
            try:
                header, encoded = url.split(",", 1)
                raw = base64.b64decode(encoded, validate=True)
            except (ValueError, binascii.Error) as exc:
                raise ValueError(
                    "reference image contains an invalid data URL"
                ) from exc
            return self._validated_data_url(
                raw, header.split(";", 1)[0].split(":", 1)[1]
            )
        if url.startswith("/") and self.settings.reference_base_url:
            url = urljoin(
                self.settings.reference_base_url.rstrip("/") + "/", url.lstrip("/")
            )
        if not url.startswith(("http://", "https://")):
            raise ValueError("reference image URL must use http, https, or data:image")
        return await self._download_reference_image(url)

    async def _download_reference_image(self, url: str) -> str:
        max_bytes = self.settings.reference_image_max_bytes
        timeout = httpx.Timeout(self.settings.reference_image_timeout)
        try:
            async with httpx.AsyncClient(
                timeout=timeout, follow_redirects=True
            ) as client:
                async with client.stream("GET", url) as response:
                    response.raise_for_status()
                    content_type = (
                        response.headers.get("content-type", "")
                        .split(";", 1)[0]
                        .lower()
                    )
                    if not content_type.startswith("image/"):
                        raise ValueError(
                            f"reference URL returned non-image content type: {content_type or 'unknown'}"
                        )
                    length = response.headers.get("content-length")
                    if length and int(length) > max_bytes:
                        raise ValueError(f"reference image exceeds {max_bytes} bytes")
                    chunks: list[bytes] = []
                    size = 0
                    async for chunk in response.aiter_bytes():
                        size += len(chunk)
                        if size > max_bytes:
                            raise ValueError(
                                f"reference image exceeds {max_bytes} bytes"
                            )
                        chunks.append(chunk)
        except httpx.HTTPError as exc:
            raise ValueError(f"failed to download reference image: {exc}") from exc
        return self._validated_data_url(b"".join(chunks), content_type)

    @staticmethod
    def _validated_data_url(raw: bytes, declared_mime: str) -> str:
        try:
            with Image.open(io.BytesIO(raw)) as image:
                image.verify()
                detected = (image.format or "").upper()
        except (UnidentifiedImageError, OSError) as exc:
            raise ValueError("reference payload is not a valid image") from exc
        mime = {
            "JPEG": "image/jpeg",
            "PNG": "image/png",
            "WEBP": "image/webp",
            "GIF": "image/gif",
        }.get(detected)
        if not mime:
            raise ValueError(
                f"unsupported reference image format: {detected or declared_mime}"
            )
        return f"data:{mime};base64,{base64.b64encode(raw).decode('ascii')}"

    @staticmethod
    def _asset_kind(asset: Any) -> str:
        if getattr(asset, "source", None) == "default_mmb_bear":
            return "character"
        return asset.kind

    @classmethod
    def _reference_stats(
        cls, request: GeneratePosterRequest, loaded: int, default_bear: int
    ) -> dict[str, int]:
        return {
            "requested": len(request.assets),
            "loaded": loaded,
            "character": sum(
                cls._asset_kind(asset) == "character" for asset in request.assets
            ),
            "scene": sum(cls._asset_kind(asset) == "scene" for asset in request.assets),
            "other": sum(cls._asset_kind(asset) == "other" for asset in request.assets),
            "default_bear": default_bear,
            "generated_character": sum(
                asset.source == "generated_character" for asset in request.assets
            ),
        }

    @staticmethod
    def _reference_instructions(prompt: str, stats: dict[str, int]) -> str:
        if stats["loaded"] == 0:
            return prompt
        return (
            f"{prompt}\n\nReference-image priority is strict: character identity first, scene structure second, "
            "product/clothing/style references third, and text only fills missing details. Preserve recognizable faces, "
            "body proportions, colors, clothing, spatial layout, lighting, and core objects from their corresponding images. "
            "Redraw only as needed for the requested action, composition, and aspect ratio. Do not replace an anchored "
            "character or scene with a newly invented one."
        )

    def _find_image_base64(self, value: Any) -> str | None:
        if isinstance(value, dict):
            if value.get("type") == "image_generation_call" and isinstance(
                value.get("result"), str
            ):
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

    def _default_bear_reference_data_url(
        self, request: GeneratePosterRequest
    ) -> str | None:
        if not self.settings.default_bear_reference_enabled:
            return None
        if not should_use_default_bear(request):
            return None
        return self._built_in_bear_data_url()

    def _built_in_bear_data_url(self) -> str | None:
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
        async with httpx.AsyncClient(
            timeout=self.settings.image_request_timeout
        ) as client:
            response = await client.post(url, headers=headers, json=payload)
            if response.status_code >= 400:
                detail = response.text[:1000]
                raise RuntimeError(
                    f"image request failed with HTTP {response.status_code}: {detail}"
                )
            return response.json()
