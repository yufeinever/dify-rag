from __future__ import annotations

import json
import mimetypes
import os
import re
from collections.abc import Generator
from typing import Any

from dify_plugin import Tool
from dify_plugin.entities.tool import ToolInvokeMessage


IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg"}
ID_KEYS = (
    "upload_file_id",
    "related_id",
    "datasource_file_id",
    "file_id",
    "id",
    "reference",
    "remote_id",
)


class MmbImageAssetBinderTool(Tool):
    def _invoke(self, tool_parameters: dict[str, Any]) -> Generator[ToolInvokeMessage, None, None]:
        source_file = tool_parameters.get("file")
        if source_file is None:
            raise ValueError("file is required")

        caption_text = self._as_text(tool_parameters.get("caption_text")).strip()
        if not caption_text:
            raise ValueError("caption_text is required")

        filename = self._first_present(
            self._read_value(source_file, "filename"),
            self._read_value(source_file, "name"),
            "image",
        )
        extension = os.path.splitext(str(filename))[1].lower()
        if extension not in IMAGE_EXTENSIONS:
            raise ValueError(f"Unsupported image extension {extension}. Supported extensions: {sorted(IMAGE_EXTENSIONS)}")

        blob = self._read_value(source_file, "blob") or b""
        original_size = self._first_present(
            self._read_value(source_file, "size"),
            self._read_value(source_file, "file_size"),
            len(blob),
        )
        mime_type = self._first_present(
            self._read_value(source_file, "mime_type"),
            self._read_value(source_file, "mimetype"),
            self._read_value(source_file, "type"),
            mimetypes.guess_type(str(filename))[0],
            "image/jpeg" if extension in {".jpg", ".jpeg"} else "image/png",
        )

        file_id, id_source = self._extract_upload_file_id(source_file)
        preprocess_metadata = self._parse_metadata(tool_parameters.get("preprocess_metadata"))

        asset_binding = {
            "parser": "mmb-image-asset-binder",
            "original_filename": filename,
            "original_file_id": file_id,
            "original_preview_path": f"/files/{file_id}/image-preview" if file_id else "",
            "extension": extension.lstrip("."),
            "mime_type": mime_type,
            "size_bytes": original_size,
            "id_source": id_source,
            "preprocess_metadata": preprocess_metadata,
        }

        text = self._format_bound_text(caption_text, asset_binding)
        report = {
            "parser": "mmb-image-asset-binder",
            "bound": bool(file_id),
            "id_source": id_source,
            "warnings": [] if file_id else ["original upload file id is unavailable; preview path was not generated"],
        }

        yield self.create_variable_message("text", text)
        yield self.create_variable_message("asset_binding", asset_binding)
        yield self.create_variable_message("asset_binding_report", report)
        yield self.create_text_message(text)
        yield self.create_json_message({"text": text, "asset_binding": asset_binding, "asset_binding_report": report})

    @classmethod
    def _extract_upload_file_id(cls, file: Any) -> tuple[str, str]:
        seen: list[tuple[str, Any]] = []
        for key in ID_KEYS:
            value = cls._read_value(file, key)
            seen.append((key, value))
            normalized = cls._normalize_id(value)
            if normalized:
                return normalized, key

        for key, value in seen:
            if value:
                parsed = cls._parse_id_from_text(str(value))
                if parsed:
                    return parsed, f"{key}:parsed"
        return "", ""

    @staticmethod
    def _read_value(obj: Any, key: str) -> Any:
        if obj is None:
            return None
        if isinstance(obj, dict):
            return obj.get(key)
        value = getattr(obj, key, None)
        if value is not None:
            return value
        data = getattr(obj, "model_dump", None)
        if callable(data):
            try:
                dumped = data()
                if isinstance(dumped, dict):
                    return dumped.get(key)
            except Exception:
                return None
        data = getattr(obj, "dict", None)
        if callable(data):
            try:
                dumped = data()
                if isinstance(dumped, dict):
                    return dumped.get(key)
            except Exception:
                return None
        return None

    @staticmethod
    def _normalize_id(value: Any) -> str:
        if value is None:
            return ""
        if isinstance(value, (bytes, bytearray)):
            try:
                value = value.decode("utf-8")
            except Exception:
                return ""
        text = str(value).strip()
        if not text:
            return ""
        if re.fullmatch(r"[0-9a-fA-F-]{32,36}", text):
            return text
        return ""

    @staticmethod
    def _parse_id_from_text(text: str) -> str:
        match = re.search(r"/files/([0-9a-fA-F-]{32,36})/(?:image-preview|file-preview|download)", text)
        if match:
            return match.group(1)
        match = re.search(r"(?:upload_file_id|related_id|file_id|id)['\"=: ]+([0-9a-fA-F-]{32,36})", text)
        if match:
            return match.group(1)
        return ""

    @staticmethod
    def _first_present(*values: Any) -> Any:
        for value in values:
            if value is not None and value != "":
                return value
        return ""

    @classmethod
    def _parse_metadata(cls, value: Any) -> Any:
        if value is None or value == "":
            return {}
        if isinstance(value, (dict, list)):
            return value
        text = cls._as_text(value).strip()
        if not text:
            return {}
        try:
            return json.loads(text)
        except Exception:
            return text

    @staticmethod
    def _as_text(value: Any) -> str:
        if value is None:
            return ""
        if isinstance(value, str):
            return value
        if isinstance(value, (dict, list)):
            return json.dumps(value, ensure_ascii=False)
        return str(value)

    @staticmethod
    def _format_bound_text(caption_text: str, asset_binding: dict[str, Any]) -> str:
        lines = [caption_text.rstrip(), "", "# 原图资产绑定"]
        lines.extend(
            [
                f"- 原图文件名: {asset_binding.get('original_filename') or ''}",
                f"- 原图文件ID: {asset_binding.get('original_file_id') or ''}",
                f"- 原图预览路径: {asset_binding.get('original_preview_path') or ''}",
                f"- 文件扩展名: {asset_binding.get('extension') or ''}",
                f"- MIME: {asset_binding.get('mime_type') or ''}",
                f"- 文件大小: {asset_binding.get('size_bytes') or 0} bytes",
            ]
        )
        if not asset_binding.get("original_file_id"):
            lines.append("- 绑定状态: 未获取到原始上传文件 ID，无法生成稳定原图预览路径")
        return "\n".join(lines).strip() + "\n"
