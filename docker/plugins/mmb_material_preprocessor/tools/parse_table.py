from __future__ import annotations

import os
from collections.abc import Generator
from typing import Any

from dify_plugin import Tool
from dify_plugin.entities.tool import ToolInvokeMessage

from tools.table_parser import SUPPORTED_TABLE_EXTENSIONS, parse_table_file


class MmbTableParserTool(Tool):
    def _invoke(self, tool_parameters: dict[str, Any]) -> Generator[ToolInvokeMessage, None, None]:
        source_file = tool_parameters.get("file")
        if source_file is None:
            raise ValueError("file is required")

        filename = getattr(source_file, "filename", "document") or "document"
        extension = os.path.splitext(filename)[1].lower()
        if extension not in SUPPORTED_TABLE_EXTENSIONS:
            raise ValueError(
                f"Unsupported table extension {extension}. Supported extensions: {sorted(SUPPORTED_TABLE_EXTENSIONS)}"
            )

        result = parse_table_file(filename, getattr(source_file, "blob", b"") or b"")
        yield self.create_variable_message("table_metadata", result.table_metadata)
        yield self.create_variable_message("parse_report", result.parse_report)
        yield self.create_text_message(result.text)
        yield self.create_json_message(
            {
                "table_metadata": result.table_metadata,
                "parse_report": result.parse_report,
                "content_list": result.content_list,
            }
        )
