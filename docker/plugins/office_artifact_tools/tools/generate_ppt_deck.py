from __future__ import annotations

from collections.abc import Generator
from typing import Any

from dify_plugin import Tool
from dify_plugin.entities.tool import ToolInvokeMessage

from tools.artifact_builder import build_pptx_artifact


class GeneratePptDeckTool(Tool):
    def _invoke(self, tool_parameters: dict[str, Any]) -> Generator[ToolInvokeMessage, None, None]:
        artifact = build_pptx_artifact(
            title=str(tool_parameters.get("title") or "MMB 方案"),
            markdown_outline=str(tool_parameters.get("markdown_outline") or ""),
            slides_json=str(tool_parameters.get("slides_json") or ""),
            filename=tool_parameters.get("filename"),
            theme=str(tool_parameters.get("theme") or "mmb_business"),
        )
        yield self.create_text_message(
            f"已生成 PPT：{artifact.filename}\n"
            f"页数：{artifact.summary['slides']}\n"
            "请在下方附件卡片下载。"
        )
        yield self.create_json_message({"filename": artifact.filename, "summary": artifact.summary})
        yield self.create_blob_message(
            artifact.blob,
            meta={"mime_type": artifact.mime_type, "filename": artifact.filename},
        )
