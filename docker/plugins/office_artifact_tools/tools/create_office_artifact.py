from __future__ import annotations

from collections.abc import Generator
from typing import Any

from dify_plugin import Tool
from dify_plugin.entities.tool import ToolInvokeMessage

from tools.artifact_builder import build_office_artifact


class CreateOfficeArtifactTool(Tool):
    def _invoke(self, tool_parameters: dict[str, Any]) -> Generator[ToolInvokeMessage, None, None]:
        artifact_type = str(tool_parameters.get("artifact_type") or "").strip().lower()
        artifact = build_office_artifact(
            artifact_type=artifact_type,
            title=str(tool_parameters.get("title") or "MMB 文件"),
            content=str(tool_parameters.get("content") or ""),
            filename=tool_parameters.get("filename"),
            sheets_json=str(tool_parameters.get("sheets_json") or ""),
            slides_json=str(tool_parameters.get("slides_json") or ""),
            style_preset=str(tool_parameters.get("style_preset") or ""),
            theme=str(tool_parameters.get("theme") or ""),
        )
        summary = artifact.summary
        detail = []
        if "tables" in summary:
            detail.append(f"表格：{summary['tables']}")
        if "slides" in summary:
            detail.append(f"页数：{summary['slides']}")
        if "sheets" in summary:
            detail.append(f"工作表：{summary['sheets']}")
        if "rows" in summary:
            detail.append(f"数据行：{summary['rows']}")
        detail.append(f"大小：{summary['size_bytes']} bytes")
        yield self.create_text_message(f"已生成文件：{artifact.filename}\n" + "\n".join(detail) + "\n请在下方附件卡片下载。")
        yield self.create_json_message({"filename": artifact.filename, "artifact_type": artifact_type, "summary": summary})
        yield self.create_blob_message(
            artifact.blob,
            meta={"mime_type": artifact.mime_type, "filename": artifact.filename},
        )
