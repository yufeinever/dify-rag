from __future__ import annotations

from collections.abc import Generator
from typing import Any

from dify_plugin import Tool
from dify_plugin.entities.tool import ToolInvokeMessage

from tools.artifact_builder import build_xlsx_artifact


class GenerateExcelWorkbookTool(Tool):
    def _invoke(self, tool_parameters: dict[str, Any]) -> Generator[ToolInvokeMessage, None, None]:
        artifact = build_xlsx_artifact(
            title=str(tool_parameters.get("title") or "MMB 表格"),
            sheets_json=str(tool_parameters.get("sheets_json") or ""),
            table_markdown=str(tool_parameters.get("table_markdown") or ""),
            filename=tool_parameters.get("filename"),
            style_preset=str(tool_parameters.get("style_preset") or "business_table"),
        )
        yield self.create_text_message(
            f"已生成 Excel 表格：{artifact.filename}\n"
            f"工作表：{artifact.summary['sheets']}\n"
            f"数据行：{artifact.summary['rows']}\n"
            "请在下方附件卡片下载。"
        )
        yield self.create_json_message({"filename": artifact.filename, "summary": artifact.summary})
        yield self.create_blob_message(
            artifact.blob,
            meta={"mime_type": artifact.mime_type, "filename": artifact.filename},
        )
