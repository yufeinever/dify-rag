from __future__ import annotations

import base64
import hashlib
import hmac
import os
import time
from pathlib import Path
from typing import Any, Protocol

from .config import Settings

THUMBNAIL_EXTENSIONS = {"bmp", "jpeg", "jpg", "png", "webp"}


class UploadFileLookup(Protocol):
    def get_upload_file(self, upload_file_id: str) -> dict[str, Any] | None: ...


class MediaAccessError(Exception):
    def __init__(self, status_code: int, message: str) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.message = message


def normalize_thumbnail_width(settings: Settings, width: int | None = None) -> int:
    requested = int(width or settings.thumbnail_default_width)
    return min(max(requested, 64), settings.thumbnail_max_width)


def normalize_thumbnail_quality(settings: Settings, quality: int | None = None) -> int:
    requested = int(quality or settings.thumbnail_default_quality)
    return min(max(requested, 40), 95)


def sign_material_thumbnail_url(
    settings: Settings,
    upload_file_id: str,
    width: int | None = None,
    quality: int | None = None,
) -> str | None:
    secret_key = settings.dify_file_preview_secret_key
    if not secret_key:
        return None
    width = normalize_thumbnail_width(settings, width)
    quality = normalize_thumbnail_quality(settings, quality)
    prefix = (settings.thumbnail_public_prefix or "/material-agent/media").rstrip("/")
    base_url = f"{prefix}/thumbnails/{upload_file_id}.webp?w={width}&q={quality}"
    timestamp = str(int(time.time()))
    nonce = os.urandom(16).hex()
    sign = _sign(secret_key, upload_file_id, width, quality, timestamp, nonce)
    return f"{base_url}&timestamp={timestamp}&nonce={nonce}&sign={sign}"


def verify_material_thumbnail_signature(
    settings: Settings,
    upload_file_id: str,
    width: int,
    quality: int,
    timestamp: str | None,
    nonce: str | None,
    sign: str | None,
) -> None:
    secret_key = settings.dify_file_preview_secret_key
    if not secret_key:
        raise MediaAccessError(403, "thumbnail signing is not configured")
    if not timestamp or not nonce or not sign:
        raise MediaAccessError(403, "missing thumbnail signature")
    try:
        signed_at = int(timestamp)
    except ValueError as exc:
        raise MediaAccessError(403, "invalid thumbnail timestamp") from exc
    ttl = max(int(settings.dify_file_preview_ttl_seconds or 300), 1)
    if int(time.time()) - signed_at > ttl:
        raise MediaAccessError(403, "thumbnail signature expired")
    expected = _sign(secret_key, upload_file_id, width, quality, timestamp, nonce)
    if not hmac.compare_digest(sign, expected):
        raise MediaAccessError(403, "invalid thumbnail signature")


def _sign(secret_key: str, upload_file_id: str, width: int, quality: int, timestamp: str, nonce: str) -> str:
    payload = f"material-thumbnail|{upload_file_id}|{width}|{quality}|{timestamp}|{nonce}"
    digest = hmac.new(secret_key.encode(), payload.encode(), hashlib.sha256).digest()
    return base64.urlsafe_b64encode(digest).decode()


class MediaThumbnailService:
    def __init__(self, settings: Settings, upload_lookup: UploadFileLookup) -> None:
        self.settings = settings
        self.upload_lookup = upload_lookup
        self.app_root = settings.app_root.resolve()
        self.cache_dir = settings.media_cache_dir.resolve()
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def render_thumbnail(
        self,
        upload_file_id: str,
        width: int | None,
        quality: int | None,
        timestamp: str | None,
        nonce: str | None,
        sign: str | None,
    ) -> Path:
        width = normalize_thumbnail_width(self.settings, width)
        quality = normalize_thumbnail_quality(self.settings, quality)
        verify_material_thumbnail_signature(self.settings, upload_file_id, width, quality, timestamp, nonce, sign)
        upload_file = self.upload_lookup.get_upload_file(upload_file_id)
        if not upload_file:
            raise MediaAccessError(404, "upload file not found")
        extension = str(upload_file.get("extension") or "").strip().lower().lstrip(".")
        if extension not in THUMBNAIL_EXTENSIONS:
            raise MediaAccessError(415, "thumbnail is not supported for this file type")
        source = self._resolve_upload_file(upload_file)
        stat = source.stat()
        cache_path = self.cache_dir / f"{upload_file_id}-{stat.st_size}-{stat.st_mtime_ns}-w{width}-q{quality}.webp"
        if cache_path.is_file():
            return cache_path
        self._generate_webp(source, cache_path, width, quality)
        return cache_path

    def _resolve_upload_file(self, upload_file: dict[str, Any]) -> Path:
        key = str(upload_file.get("key") or "").strip()
        if not key:
            raise MediaAccessError(404, "upload file has no storage key")
        candidate = (self.app_root / "storage" / key).resolve()
        storage_root = (self.app_root / "storage").resolve()
        if candidate != storage_root and storage_root not in candidate.parents:
            raise MediaAccessError(403, "upload file path escapes storage root")
        if not candidate.is_file():
            raise MediaAccessError(404, "upload file content not found")
        return candidate

    def _generate_webp(self, source: Path, cache_path: Path, width: int, quality: int) -> None:
        from PIL import Image, ImageOps

        try:
            with Image.open(source) as image:
                if getattr(image, "is_animated", False):
                    raise MediaAccessError(415, "animated images are not supported for thumbnails")
                image = ImageOps.exif_transpose(image)
                image.thumbnail((width, width), Image.Resampling.LANCZOS)
                if image.mode not in {"RGB", "RGBA"}:
                    has_alpha = "A" in image.getbands() or "transparency" in image.info
                    image = image.convert("RGBA" if has_alpha else "RGB")
                tmp_path = cache_path.with_suffix(cache_path.suffix + ".tmp")
                image.save(tmp_path, format="WEBP", quality=quality, method=6)
                tmp_path.replace(cache_path)
        except MediaAccessError:
            raise
        except Exception as exc:
            raise MediaAccessError(415, "unable to generate thumbnail") from exc