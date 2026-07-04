from __future__ import annotations

import os
from collections.abc import Generator
from typing import Any

from dify_plugin import Tool
from dify_plugin.entities.tool import ToolInvokeMessage

from tools.visual_ppt_builder import OpenAIImageConfig, build_visual_ppt_artifact


class CreateVisualPptDeckTool(Tool):
    def _invoke(self, tool_parameters: dict[str, Any]) -> Generator[ToolInvokeMessage, None, None]:
        credentials = self.runtime.credentials or {}
        image_model = (
            str(tool_parameters.get("image_model") or "").strip()
            or credentials.get("openai_image_model")
            or os.environ.get("OPENAI_IMAGE_MODEL")
            or "gpt-image-2"
        )
        quality = (
            str(tool_parameters.get("quality") or "").strip()
            or credentials.get("openai_image_quality")
            or os.environ.get("OPENAI_IMAGE_QUALITY")
            or "medium"
        )
        image_config = OpenAIImageConfig(
            api_key=credentials.get("openai_api_key") or os.environ.get("OPENAI_API_KEY") or "",
            api_base=credentials.get("openai_api_base") or os.environ.get("OPENAI_API_BASE") or "https://api.openai.com/v1",
            model=image_model,
            quality=quality,
        )
        artifact = build_visual_ppt_artifact(
            title=str(tool_parameters.get("title") or "MMB 视觉PPT"),
            outline=str(tool_parameters.get("outline") or ""),
            slides_json=str(tool_parameters.get("slides_json") or ""),
            filename=tool_parameters.get("filename"),
            slide_count=tool_parameters.get("slide_count"),
            style_preset=str(tool_parameters.get("style_preset") or "mmb_modern_pitch"),
            image_config=image_config,
            image_concurrency=tool_parameters.get("image_concurrency"),
        )
        summary = artifact.summary
        yield self.create_text_message(
            "已生成视觉 PPT：{filename}\n页数：{slides}\n风格：{style}\n大小：{size} bytes\n请在下方附件卡片下载。".format(
                filename=artifact.filename,
                slides=summary["slides"],
                style=summary["style"],
                size=summary["size_bytes"],
            )
        )
        yield self.create_json_message({"filename": artifact.filename, "summary": summary})
        yield self.create_blob_message(
            artifact.blob,
            meta={"mime_type": artifact.mime_type, "filename": artifact.filename},
        )
