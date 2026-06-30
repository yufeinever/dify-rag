from __future__ import annotations

import csv
import io
import logging
from collections.abc import Sequence
from html.parser import HTMLParser
from typing import Any

import charset_normalizer
import pandas as pd

from graphon.file import File
from graphon.nodes.document_extractor import UnstructuredApiConfig
from graphon.nodes.document_extractor import node as document_extractor_node

logger = logging.getLogger(__name__)

_TABLE_EXTENSIONS = {".csv", ".xls", ".xlsx"}
_TABLE_MIME_TYPES = {
    "text/csv",
    "application/csv",
    "application/vnd.ms-excel",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
}
_ORIGINAL_EXTRACT_TEXT_FROM_FILE = document_extractor_node._extract_text_from_file


def apply_document_extractor_table_patch() -> None:
    """Route table files through search-friendly row text in graphon document extractor."""
    if getattr(document_extractor_node._extract_text_from_file, "_mmb_table_patch", False):
        return
    document_extractor_node._extract_text_from_file = _extract_text_from_file_with_table_rows
    document_extractor_node._extract_text_from_file._mmb_table_patch = True


def _extract_text_from_file_with_table_rows(
    http_client,
    file: File,
    *,
    unstructured_api_config: UnstructuredApiConfig,
) -> str:
    extension = (getattr(file, "extension", None) or "").lower()
    mime_type = (getattr(file, "mime_type", None) or "").lower()
    if extension not in _TABLE_EXTENSIONS and mime_type not in _TABLE_MIME_TYPES:
        return _ORIGINAL_EXTRACT_TEXT_FROM_FILE(
            http_client,
            file,
            unstructured_api_config=unstructured_api_config,
        )

    file_content = document_extractor_node._download_file_content(http_client, file)
    file_name = getattr(file, "filename", None) or getattr(file, "name", None) or ""
    if extension == ".csv" or mime_type in {"text/csv", "application/csv"}:
        return _extract_csv_rows(file_content, file_name)
    return _extract_excel_rows(file_content, file_name)


def _extract_csv_rows(file_content: bytes, file_name: str) -> str:
    text = _decode_text(file_content)
    rows = list(csv.reader(io.StringIO(text)))
    if not rows:
        return ""

    headers = [_clean_value(cell) or f"Column {idx + 1}" for idx, cell in enumerate(rows[0])]
    documents: list[str] = []
    for row_number, row in enumerate(rows[1:], start=2):
        if not any(_clean_value(cell) for cell in row):
            continue
        fields = []
        for idx, header in enumerate(headers):
            value = row[idx] if idx < len(row) else ""
            if _clean_value(value):
                fields.append((header, _clean_value(value)))
        if fields:
            documents.append(_format_row(file_name=file_name, sheet_name="CSV", row_number=row_number, fields=fields))
    return "\n\n".join(documents)


def _extract_excel_rows(file_content: bytes, file_name: str) -> str:
    if _looks_like_html(file_content):
        return _extract_html_table_rows(file_content, file_name)


    return _extract_excel_rows_with_pandas(file_content, file_name)


def _extract_excel_rows_with_pandas(
    file_content: bytes, file_name: str, source_ranges: dict[str, tuple[str, str, str]] | None = None
) -> str:
    try:
        excel_file = pd.ExcelFile(io.BytesIO(file_content))
    except Exception as exc:
        msg = f"Failed to extract text from Excel file: {exc!s}"
        raise document_extractor_node.TextExtractionError(msg) from exc

    documents: list[str] = []
    for sheet_name in excel_file.sheet_names:
        try:
            df = excel_file.parse(sheet_name=sheet_name)
        except (TypeError, ValueError):
            continue
        if not isinstance(df, pd.DataFrame):
            continue

        df = df.dropna(how="all")
        if df.empty:
            continue
        df.columns = pd.Index([_clean_value(col) or f"Column {idx + 1}" for idx, col in enumerate(df.columns)])

        for row_index, row in df.iterrows():
            fields = []
            for column in df.columns:
                value = row[column]
                if pd.isna(value):
                    continue
                value_text = _clean_value(value)
                if value_text:
                    fields.append((str(column), value_text))
            if fields:
                row_number = int(row_index) + 2
                documents.append(
                    _format_row(
                        file_name=file_name,
                        sheet_name=str(sheet_name),
                        row_number=row_number,
                        source_uri=_row_source_uri(file_name, str(sheet_name), row_number, source_ranges),
                        fields=fields,
                    )
                )
    return "\n\n".join(documents)


def _row_source_uri(
    file_name: str, sheet_name: str, row_number: int, source_ranges: dict[str, tuple[str, str, str]] | None
) -> str:
    if not source_ranges or sheet_name not in source_ranges:
        return ""
    prefix, start_col, end_col = source_ranges[sheet_name]
    source_file = prefix or file_name
    return f"{source_file}#{sheet_name}!{start_col}{row_number}:{end_col}{row_number}"


def _format_row(
    *, file_name: str, sheet_name: str, row_number: int, fields: Sequence[tuple[str, str]], source_uri: str = ""
) -> str:
    lines = []
    if file_name:
        lines.append(f"File: {file_name}")
    lines.extend([f"Sheet: {sheet_name}", f"Row: {row_number}"])
    if source_uri:
        lines.append(f"Source: {source_uri}")
    lines.extend(f"{name}: {value}" for name, value in fields)
    return "\n".join(lines)


def _extract_html_table_rows(file_content: bytes, file_name: str) -> str:
    parser = _HTMLTableParser()
    parser.feed(_decode_text(file_content))

    documents: list[str] = []
    for table_index, table in enumerate(parser.tables, start=1):
        rows = _trim_empty_rows(table)
        if not rows:
            continue
        headers = [_clean_value(cell) or f"Column {idx + 1}" for idx, cell in enumerate(rows[0])]
        for row_number, row in enumerate(rows[1:], start=2):
            fields = []
            for idx, header in enumerate(headers):
                value = row[idx] if idx < len(row) else ""
                value_text = _clean_value(value)
                if value_text:
                    fields.append((header, value_text))
            if fields:
                documents.append(
                    _format_row(
                        file_name=file_name,
                        sheet_name=f"HTML Table {table_index}",
                        row_number=row_number,
                        fields=fields,
                    )
                )
    return "\n\n".join(documents)


def _decode_text(file_content: bytes) -> str:
    result = charset_normalizer.from_bytes(file_content).best()
    encoding = result.encoding if result and result.encoding else "utf-8"
    text = file_content.decode(encoding, errors="ignore")
    return text.lstrip("\ufeff")


def _looks_like_html(file_content: bytes) -> bool:
    prefix = _decode_text(file_content[:4096]).lstrip().lower()
    return prefix.startswith(("<!doctype html", "<html", "<table"))


def _trim_empty_rows(rows: Sequence[Sequence[Any]]) -> list[list[Any]]:
    return [list(row) for row in rows if any(_clean_value(cell) for cell in row)]


class _HTMLTableParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.tables: list[list[list[str]]] = []
        self._table_stack = 0
        self._current_table: list[list[str]] | None = None
        self._current_row: list[str] | None = None
        self._current_cell: list[str] | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "table":
            self._table_stack += 1
            if self._table_stack == 1:
                self._current_table = []
        elif tag == "tr" and self._table_stack == 1:
            self._current_row = []
        elif tag in {"td", "th"} and self._table_stack == 1 and self._current_row is not None:
            self._current_cell = []

    def handle_data(self, data: str) -> None:
        if self._current_cell is not None:
            self._current_cell.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag in {"td", "th"} and self._current_cell is not None and self._current_row is not None:
            self._current_row.append(_clean_value("".join(self._current_cell)))
            self._current_cell = None
        elif tag == "tr" and self._current_row is not None and self._current_table is not None:
            self._current_table.append(self._current_row)
            self._current_row = None
        elif tag == "table" and self._table_stack:
            if self._table_stack == 1 and self._current_table is not None:
                self.tables.append(self._current_table)
                self._current_table = None
            self._table_stack -= 1


def _clean_value(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, float) and value.is_integer():
        value = int(value)
    return " ".join(str(value).split())