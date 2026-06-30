from __future__ import annotations

import io

from openpyxl import Workbook

from core.workflow.document_extractor_table_patch import (
    _extract_csv_rows,
    _extract_excel_rows,
    _extract_html_table_rows,
)


def test_csv_document_extractor_outputs_row_context():
    result = _extract_csv_rows(
        b"project,owner,status\nAlpha,Zhang San,active\n\nBeta,Li Si,paused\n",
        "sample.csv",
    )

    assert "File: sample.csv" in result
    assert "Sheet: CSV" in result
    assert "Row: 2" in result
    assert "project: Alpha" in result
    assert "owner: Zhang San" in result
    assert "Row: 4" in result
    assert "status: paused" in result


def test_xlsx_document_extractor_outputs_sheet_and_row_context():
    wb = Workbook()
    ws = wb.active
    ws.title = "Projects"
    ws.append(["project", "owner", "amount"])
    ws.append(["Alpha", "Zhang San", 1200])
    ws.append([None, None, None])
    notes = wb.create_sheet("Notes")
    notes.append(["note_id", "text"])
    notes.append([1, "xlsx-needle-0630"])
    buffer = io.BytesIO()
    wb.save(buffer)

    result = _extract_excel_rows(buffer.getvalue(), "sample.xlsx")

    assert "File: sample.xlsx" in result
    assert "Sheet: Projects" in result
    assert "Row: 2" in result
    assert "project: Alpha" in result
    assert "amount: 1200" in result
    assert "Sheet: Notes" in result
    assert "text: xlsx-needle-0630" in result


def test_html_xls_document_extractor_outputs_table_rows():
    result = _extract_html_table_rows(
        b'<html><body><table><tr><th>project</th><th>keyword</th></tr>'
        b'<tr><td>Gamma</td><td>xls-needle-0630</td></tr></table></body></html>',
        "sample.xls",
    )

    assert "File: sample.xls" in result
    assert "Sheet: HTML Table 1" in result
    assert "Row: 2" in result
    assert "project: Gamma" in result
    assert "keyword: xls-needle-0630" in result