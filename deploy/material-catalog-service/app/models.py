from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import NotRequired, TypedDict


TEXT_EXTENSIONS = {".txt", ".md", ".html", ".htm", ".json", ".csv"}
DOCUMENT_EXTENSIONS = {".pdf", ".doc", ".docx", ".ppt", ".pptx", ".xls", ".xlsx"}
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".gif", ".bmp", ".tif", ".tiff"}


class AssetRecord(TypedDict):
    path: str
    relative_path: str
    root: str
    name: str
    extension: str
    size: int
    mtime: float
    sha256: NotRequired[str]
    fingerprint: str
    status: str
    version: int
    first_seen_at: str
    last_seen_at: str
    last_changed_at: str


class PreprocessRecommendation(TypedDict):
    material_type: str
    action: str
    reason: str
    priority: str


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def classify_extension(extension: str) -> str:
    ext = extension.lower()
    if ext in IMAGE_EXTENSIONS:
        return "image"
    if ext in {".pdf"}:
        return "pdf"
    if ext in {".ppt", ".pptx"}:
        return "presentation"
    if ext in {".doc", ".docx"}:
        return "word_document"
    if ext in {".xls", ".xlsx", ".csv"}:
        return "table"
    if ext in TEXT_EXTENSIONS:
        return "text"
    if ext in DOCUMENT_EXTENSIONS:
        return "document"
    return "unknown"


def recommend_preprocessing(extension: str, size: int) -> PreprocessRecommendation:
    material_type = classify_extension(extension)
    if material_type == "pdf":
        return {
            "material_type": material_type,
            "action": "Use MinerU or equivalent layout-aware PDF parsing before chunking.",
            "reason": "PDF files often contain mixed layout, figures, and tables; raw text extraction is not enough.",
            "priority": "high" if size > 1_000_000 else "medium",
        }
    if material_type == "presentation":
        return {
            "material_type": material_type,
            "action": "Convert slides to structured text plus slide images, then summarize by slide section.",
            "reason": "PPT files usually carry meaning in layout and visuals, not only speaker text.",
            "priority": "high",
        }
    if material_type == "image":
        return {
            "material_type": material_type,
            "action": "Generate visual captions and OCR text before deciding whether to ingest into a knowledge base.",
            "reason": "Image assets need a text surrogate for retrieval and agent planning.",
            "priority": "medium",
        }
    if material_type == "word_document":
        return {
            "material_type": material_type,
            "action": "Extract headings, paragraphs, and tables; preserve document title and section hierarchy.",
            "reason": "Word documents are usually text-rich and benefit from hierarchy-aware chunking.",
            "priority": "medium",
        }
    if material_type == "table":
        return {
            "material_type": material_type,
            "action": "Parse tables as structured rows and produce a compact schema/summary before RAG ingestion.",
            "reason": "Spreadsheets and CSV files should not be flattened into arbitrary text chunks.",
            "priority": "medium",
        }
    if material_type == "text":
        return {
            "material_type": material_type,
            "action": "Lightweight text cleaning and chunking is enough unless the file is a machine export.",
            "reason": "Plain text already has a usable retrieval representation.",
            "priority": "low",
        }
    return {
        "material_type": material_type,
        "action": "Inspect manually or add a parser before ingestion.",
        "reason": "The file type is not covered by the standard preprocessing rules.",
        "priority": "low",
    }


def relative_to_root(path: Path, app_root: Path) -> str:
    return path.resolve().relative_to(app_root.resolve()).as_posix()
