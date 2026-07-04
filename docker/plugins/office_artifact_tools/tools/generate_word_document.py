from __future__ import annotations

import json
from collections.abc import Generator
from typing import Any

from dify_plugin import Tool
from dify_plugin.entities.tool import ToolInvokeMessage

from tools.artifact_builder import build_docx_artifact


class GenerateWordDocumentTool(Tool):
    def _invoke(self, tool_parameters: dict[str, Any]) -> Generator[ToolInvokeMessage, None, None]:
        artifact = build_docx_artifact(
            title=str(tool_parameters.get("title") or "生成文档"),
            markdown_content=str(tool_parameters.get("markdown_content") or ""),
            filename=tool_parameters.get("filename"),
            style_preset=str(tool_parameters.get("style_preset") or "business_brief"),
        )
        yield self.create_text_message(
            f"已生成 Word 文档：{artifact.filename}\n"
            f"大小：{artifact.summary['size_bytes']} bytes\n"
            "请在下方附件卡片下载。"
        )
        yield self.create_json_message({"filename": artifact.filename, "summary": artifact.summary})
        yield self.create_blob_message(
            artifact.blob,
            meta={"mime_type": artifact.mime_type, "filename": artifact.filename},
        )
