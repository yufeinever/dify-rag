from __future__ import annotations

import io
import mimetypes
import os
from collections.abc import Generator
from typing import Any

from dify_plugin import Tool
from dify_plugin.entities.tool import ToolInvokeMessage
from PIL import Image, ImageOps


IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg"}


class MmbImagePreprocessTool(Tool):
    def _invoke(self, tool_parameters: dict[str, Any]) -> Generator[ToolInvokeMessage, None, None]:
        source_file = tool_parameters.get("file")
        if source_file is None:
            raise ValueError("file is required")

        original_name = getattr(source_file, "filename", "image") or "image"
        original_blob = getattr(source_file, "blob", b"") or b""
        extension = os.path.splitext(original_name)[1].lower()
        if extension not in IMAGE_EXTENSIONS:
            raise ValueError(f"Unsupported image extension {extension}. Supported extensions: {sorted(IMAGE_EXTENSIONS)}")

        max_long_edge = self._number(tool_parameters.get("max_long_edge"), 1600)
        jpeg_quality = self._bounded_number(tool_parameters.get("jpeg_quality"), 82, 50, 95)
        small_passthrough_kb = self._number(tool_parameters.get("small_passthrough_kb"), 512)
        force_jpeg = bool(tool_parameters.get("force_jpeg", True))

        processed_name, processed_blob, report = self._preprocess_image(
            filename=original_name,
            blob=original_blob,
            max_long_edge=max_long_edge,
            jpeg_quality=jpeg_quality,
            small_passthrough_kb=small_passthrough_kb,
            force_jpeg=force_jpeg,
        )

        file_metadata = {
            "source_file_name": original_name,
            "source_file_extension": extension.lstrip("."),
            "processed_file_name": processed_name,
            "processed_mime_type": mimetypes.guess_type(processed_name)[0] or "image/jpeg",
            "original_size_bytes": len(original_blob),
            "processed_size_bytes": len(processed_blob),
        }
        yield self.create_variable_message("file_metadata", file_metadata)
        yield self.create_variable_message("preprocess_report", report)
        yield self.create_text_message(self._format_report(file_metadata, report))
        yield self.create_json_message({"file_metadata": file_metadata, "preprocess_report": report})
        yield self.create_blob_message(
            processed_blob,
            meta={"mime_type": file_metadata["processed_mime_type"], "filename": processed_name},
        )

    @staticmethod
    def _number(value: Any, default: int) -> int:
        try:
            return int(value)
        except (TypeError, ValueError):
            return default

    @classmethod
    def _bounded_number(cls, value: Any, default: int, minimum: int, maximum: int) -> int:
        return max(minimum, min(maximum, cls._number(value, default)))

    def _preprocess_image(
        self,
        *,
        filename: str,
        blob: bytes,
        max_long_edge: int,
        jpeg_quality: int,
        small_passthrough_kb: int,
        force_jpeg: bool,
    ) -> tuple[str, bytes, dict[str, Any]]:
        report: dict[str, Any] = {
            "parser": "mmb-image-preprocess",
            "strategy": "resize-and-jpeg-copy",
            "original_filename": filename,
            "processed_filename": filename,
            "original_size_bytes": len(blob),
            "processed_size_bytes": len(blob),
            "compressed": False,
            "actions": [],
            "warnings": [],
        }

        with Image.open(io.BytesIO(blob)) as image:
            image = ImageOps.exif_transpose(image)
            original_format = image.format or "original"
            original_mode = image.mode
            original_size = image.size
            image = self._resize_image(image, max_long_edge)
            processed_size = image.size

            should_passthrough = (
                len(blob) <= small_passthrough_kb * 1024
                and max(original_size) <= max_long_edge
                and not force_jpeg
            )
            if should_passthrough:
                report["actions"].append("kept original image: below passthrough threshold")
                report.update(
                    {
                        "original_dimensions": list(original_size),
                        "processed_dimensions": list(original_size),
                        "original_mode": original_mode,
                        "processed_format": original_format,
                    }
                )
                return filename, blob, report

            if image.mode in {"RGBA", "LA", "P"}:
                rgba = image.convert("RGBA")
                background = Image.new("RGB", rgba.size, (255, 255, 255))
                background.paste(rgba, mask=rgba.split()[-1])
                image = background
                report["actions"].append("flattened alpha channel on white background")
            else:
                image = image.convert("RGB")

            out = io.BytesIO()
            image.save(out, format="JPEG", quality=jpeg_quality, optimize=True, progressive=True)
            processed_blob = out.getvalue()
            processed_name = f"{os.path.splitext(filename)[0] or 'image'}__mmb_preprocessed.jpg"

        report.update(
            {
                "processed_filename": processed_name,
                "processed_size_bytes": len(processed_blob),
                "compressed": len(processed_blob) < len(blob),
                "original_dimensions": list(original_size),
                "processed_dimensions": list(processed_size),
                "original_mode": original_mode,
                "processed_format": "JPEG",
                "jpeg_quality": jpeg_quality,
                "max_long_edge": max_long_edge,
            }
        )
        if processed_size != original_size:
            report["actions"].append(f"resized image {original_size} -> {processed_size}")
        else:
            report["actions"].append("kept original dimensions")
        report["actions"].append(f"encoded parsing copy as JPEG quality {jpeg_quality}")
        if len(processed_blob) >= len(blob):
            report["warnings"].append("processed copy is not smaller than original; kept for normalized model input")
        return processed_name, processed_blob, report

    @staticmethod
    def _resize_image(image: Image.Image, max_long_edge: int) -> Image.Image:
        width, height = image.size
        long_edge = max(width, height)
        if long_edge <= max_long_edge:
            return image.copy()
        ratio = max_long_edge / long_edge
        new_size = (max(1, int(width * ratio)), max(1, int(height * ratio)))
        return image.resize(new_size, Image.Resampling.LANCZOS)

    @staticmethod
    def _format_report(file_metadata: dict[str, Any], report: dict[str, Any]) -> str:
        return "\n".join(
            [
                "Image preprocess report",
                f"File: {file_metadata['source_file_name']}",
                f"Processed file: {file_metadata['processed_file_name']}",
                f"Original bytes: {file_metadata['original_size_bytes']}",
                f"Processed bytes: {file_metadata['processed_size_bytes']}",
                f"Dimensions: {report.get('original_dimensions')} -> {report.get('processed_dimensions')}",
                f"Actions: {'; '.join(report.get('actions', []))}",
            ]
        )
