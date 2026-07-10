from __future__ import annotations

from io import BytesIO
from pathlib import PurePath
from typing import Any
from zipfile import BadZipFile, ZipFile

import httpx

PPTX_MIME_TYPE = (
    "application/vnd.openxmlformats-officedocument.presentationml.presentation"
)
PPTX_MAX_BYTES = 30 * 1024 * 1024
PPTX_MAX_UNCOMPRESSED_BYTES = 200 * 1024 * 1024
PPTX_MAX_ENTRIES = 2_000
PPTX_REQUIRED_ENTRIES = {"[Content_Types].xml", "ppt/presentation.xml"}


class PptxArtifactError(RuntimeError):
    pass


def _value(obj: Any, name: str, default: Any = None) -> Any:
    if isinstance(obj, dict):
        return obj.get(name, default)
    return getattr(obj, name, default)


def collect_pptx_citations(output_items: Any) -> list[dict[str, str]]:
    citations: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for item in output_items or []:
        for content in _value(item, "content", []) or []:
            for annotation in _value(content, "annotations", []) or []:
                if _value(annotation, "type") != "container_file_citation":
                    continue
                container_id = str(_value(annotation, "container_id", "") or "")
                file_id = str(_value(annotation, "file_id", "") or "")
                filename = PurePath(str(_value(annotation, "filename", "") or "")).name
                if (
                    not container_id
                    or not file_id
                    or not filename.lower().endswith(".pptx")
                ):
                    continue
                key = (container_id, file_id)
                if key in seen:
                    continue
                seen.add(key)
                citations.append(
                    {
                        "container_id": container_id,
                        "file_id": file_id,
                        "filename": filename,
                    }
                )
    return citations


def validate_pptx_bytes(filename: str, content: bytes) -> None:
    if not filename.lower().endswith(".pptx"):
        raise PptxArtifactError("Only .pptx artifacts are supported.")
    if not content:
        raise PptxArtifactError("The generated PPTX is empty.")
    if len(content) > PPTX_MAX_BYTES:
        raise PptxArtifactError("The generated PPTX exceeds the 30 MiB limit.")
    try:
        with ZipFile(BytesIO(content)) as archive:
            entries = archive.infolist()
            names = {entry.filename for entry in entries}
            if not PPTX_REQUIRED_ENTRIES.issubset(names):
                raise PptxArtifactError(
                    "The generated file is not a valid PPTX package."
                )
            if not any(
                name.startswith("ppt/slides/slide") and name.endswith(".xml")
                for name in names
            ):
                raise PptxArtifactError("The generated PPTX contains no slides.")
            if len(entries) > PPTX_MAX_ENTRIES:
                raise PptxArtifactError("The generated PPTX contains too many entries.")
            if sum(entry.file_size for entry in entries) > PPTX_MAX_UNCOMPRESSED_BYTES:
                raise PptxArtifactError(
                    "The generated PPTX expands beyond the allowed size."
                )
            if archive.testzip() is not None:
                raise PptxArtifactError("The generated PPTX is corrupted.")
    except BadZipFile as exc:
        raise PptxArtifactError(
            "The generated file is not a valid PPTX package."
        ) from exc


def publish_generated_pptx(
    client: Any, response: Any, credentials: dict[str, Any]
) -> list[dict[str, Any]]:
    upload_url = str(credentials.get("pptx_artifact_upload_url") or "").strip()
    api_key = str(credentials.get("pptx_artifact_api_key") or "").strip()
    tenant_id = str(credentials.get("pptx_artifact_tenant_id") or "").strip()
    user_id = str(credentials.get("pptx_artifact_user_id") or "").strip()
    if not upload_url or not api_key or not tenant_id or not user_id:
        raise PptxArtifactError(
            "PPTX artifact upload is not configured for this model provider."
        )

    citations = collect_pptx_citations(_value(response, "output", []))
    if not citations:
        raise PptxArtifactError("The model did not return a generated .pptx file.")

    published: list[dict[str, Any]] = []
    for citation in citations:
        binary_response = client.containers.files.content.retrieve(
            citation["file_id"],
            container_id=citation["container_id"],
        )
        content = binary_response.read()
        validate_pptx_bytes(citation["filename"], content)

        upload_response = httpx.post(
            upload_url,
            headers={"Authorization": f"Bearer {api_key}"},
            data={"tenant_id": tenant_id, "user_id": user_id},
            files={"file": (citation["filename"], content, PPTX_MIME_TYPE)},
            timeout=60.0,
        )
        if upload_response.status_code != 201:
            raise PptxArtifactError(
                f"Dify rejected the generated PPTX upload with status {upload_response.status_code}."
            )
        payload = upload_response.json()
        download_url = str(payload.get("download_url") or "")
        if not download_url:
            raise PptxArtifactError(
                "Dify did not return a download URL for the generated PPTX."
            )
        published.append(payload)
    return published


def render_pptx_downloads(published: list[dict[str, Any]]) -> str:
    lines = ["", "", "### PPT 文件"]
    for artifact in published:
        filename = str(artifact.get("filename") or "演示文稿.pptx")
        download_url = str(artifact["download_url"])
        lines.append(f"- [{filename}]({download_url})")
    return "\n".join(lines)
