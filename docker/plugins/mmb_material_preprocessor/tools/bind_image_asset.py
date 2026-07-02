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

BUSINESS_TOPIC_RULES = (
    ("business_fact", "深圳文交所战略合作事实摘要", ("深圳文交所", "深圳文化产权交易所", "深圳市文化金融服务中心", "深文所", "战略合作", "合作"), "战略合作、合作关系、合作内容、合作海报"),
    ("business_fact", "加盟/投资合作事实摘要", ("加盟", "合伙", "代理", "投资", "合作方式", "加入方式", "分润", "费用", "收益"), "加盟方式、合作模式、投资合作、分润、门槛"),
    ("business_fact", "品牌/IP 业务事实摘要", ("IP", "品牌", "形象", "啤酒熊", "智慧鲜啤", "小程序", "应用场景"), "品牌/IP、视觉资产、应用场景"),
)
LOW_INFO_TERMS = {"mmb", "瞢瞢熊", "懵懵熊", "麦乐迪", "智慧鲜啤", "麦乐迪智慧鲜啤交易所"}


def _chunk_block(chunk_type: str, title: str, lines: list[str]) -> str:
    body = [line.strip() for line in lines if line and line.strip()]
    return "\n".join([f"<!-- chunk_type: {chunk_type} -->", f"### {title}", *body])


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

        explicit_file_id = self._normalize_id(tool_parameters.get("upload_file_id"))
        if explicit_file_id:
            file_id, id_source = explicit_file_id, "upload_file_id_parameter"
        else:
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

        yield self.create_text_message(text)
        yield self.create_variable_message("asset_binding", asset_binding)
        yield self.create_variable_message("asset_binding_report", report)
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
        business_summaries = MmbImageAssetBinderTool._build_business_summaries(caption_text, asset_binding)
        visual_summary = _chunk_block(
            "visual_asset",
            "图片/视觉资产说明",
            ["该片段用于图片、Logo、海报、IP形象、配图类问题。", *MmbImageAssetBinderTool._sanitize_caption_lines(caption_text)],
        )
        lines = [*business_summaries, visual_summary, "", "# 原图资产绑定"]
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

    @classmethod
    def _build_business_summaries(cls, caption_text: str, asset_binding: dict[str, Any]) -> list[str]:
        fact_lines = cls._fact_lines(caption_text)
        filename = asset_binding.get("original_filename") or "image"
        summaries: list[str] = []
        for chunk_type, title, keywords, related in BUSINESS_TOPIC_RULES:
            matched = [line for line in fact_lines if any(keyword.lower() in line.lower() for keyword in keywords)]
            if not matched:
                continue
            summaries.append(
                _chunk_block(
                    chunk_type,
                    title,
                    [
                        "相关主体：MMB、瞢瞢熊、懵懵熊、麦乐迪智慧鲜啤交易所",
                        f"相关主题：{related}",
                        "关键事实：" + "；".join(matched[:8]),
                        f"来源：{filename}，图片 OCR/视觉标注自动提取。",
                    ],
                )
            )
        return summaries[:4]

    @classmethod
    def _fact_lines(cls, caption_text: str) -> list[str]:
        lines: list[str] = []
        for raw in caption_text.splitlines():
            line = re.sub(r"^[#>*\-\s]+", "", raw).strip()
            line = re.sub(r"\s+", " ", line)
            if not line or cls._is_low_info_line(line):
                continue
            if len(re.sub(r"\s+", "", line)) < 8:
                continue
            lines.append(line[:220])
        return lines

    @classmethod
    def _sanitize_caption_lines(cls, caption_text: str) -> list[str]:
        lines: list[str] = []
        for raw in caption_text.splitlines():
            line = raw.rstrip()
            if cls._is_low_info_line(line):
                lines.append(_chunk_block("ocr_noise", "低信息 OCR/Logo 文本", [f"原始文本：{line.strip()}", "用途：仅作为视觉素材辅助信息，普通业务问答不应使用本段作为主要依据。"]))
            elif line.strip():
                lines.append(line)
        return lines

    @staticmethod
    def _is_low_info_line(text: str) -> bool:
        cleaned = re.sub(r"^[#>*\-\s]+", "", text).strip()
        cleaned = re.sub(r"[\s:：,，。;；|/\\_\-]+", " ", cleaned).strip().lower()
        if not cleaned:
            return False
        if cleaned in LOW_INFO_TERMS:
            return True
        tokens = [token for token in cleaned.split() if token]
        return 0 < len(tokens) <= 3 and all(token in LOW_INFO_TERMS or token in {"ocr文字", "ocr", "logo"} for token in tokens)
