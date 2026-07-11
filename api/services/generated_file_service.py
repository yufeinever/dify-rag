"""Generated content asset indexing, authorization, preview, and backfill services.

``GeneratedFile`` is retained as the database model name for migration compatibility,
but rows may represent either a local ``ToolFile`` or a trusted remote workflow asset.
Remote discovery is deliberately narrow: only documented workflow output fields and
approved hosts are accepted. Callers must always supply tenant and actor scope when
reading assets; a bare asset ID is never sufficient authorization.
"""

from __future__ import annotations

import hashlib
import logging
import os
import shutil
import subprocess
import tempfile
from datetime import UTC, datetime
from mimetypes import guess_extension
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit
from uuid import uuid4

from sqlalchemy import case, func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from core.helper import ssrf_proxy
from core.tools.signature import sign_tool_file
from extensions.ext_storage import storage
from graphon.file import FileTransferMethod
from models.account import Account
from models.enums import MessageFileBelongsTo
from models.model import App, EndUser, Message, MessageFile
from models.tools import GeneratedFile, ToolFile
from models.workflow import WorkflowRun
from services.generated_asset_discovery import (
    GeneratedAssetCandidate,
    extract_workflow_asset_candidates,
    extract_workflow_tool_file_ids,
    trusted_remote_asset_url,
)

logger = logging.getLogger(__name__)

IMAGE_TYPES = {"bmp", "gif", "jpeg", "jpg", "png", "svg", "webp"}
TEXT_TYPES = {"csv", "json", "log", "md", "txt", "xml", "yaml", "yml"}
OFFICE_PREVIEW_TYPES = {"doc", "docx", "ppt", "pptx", "xls", "xlsx"}
NATIVE_PREVIEW_TYPES = {*IMAGE_TYPES, *TEXT_TYPES, "pdf", "mp3", "mp4", "ogg", "wav", "webm"}
GENERATED_FILE_PREVIEW_CACHE_DIR = Path("/tmp/dify-document-previews")
MAX_PERSISTED_VIDEO_BYTES = 200 * 1024 * 1024
MP4_FILE_SIGNATURE = b"ftyp"


def classify_file_type(mime_type: str, name: str = "") -> str:
    """Return the stable asset category used by API filters and facets."""

    lower_mime = (mime_type or "").lower()
    extension = _extension_from_name_or_mime(name, mime_type).lstrip(".").lower()

    if lower_mime.startswith("image/"):
        return "image"
    if lower_mime.startswith("video/"):
        return "video"
    if lower_mime.startswith("audio/"):
        return "audio"
    if extension in {"ppt", "pptx"} or "presentation" in lower_mime or "powerpoint" in lower_mime:
        return "presentation"
    if extension in {"xls", "xlsx"} or "spreadsheet" in lower_mime or "excel" in lower_mime:
        return "spreadsheet"
    if extension in {"doc", "docx", "pdf", *TEXT_TYPES} or any(
        marker in lower_mime for marker in ("pdf", "word", "text", "json", "xml", "csv")
    ):
        return "document"
    if extension in {"zip", "rar", "7z", "tar", "gz"} or "zip" in lower_mime:
        return "archive"
    return "other"


def register_generated_file_from_message_file(
    session: Session,
    message_file: MessageFile,
    *,
    message: Message | None = None,
    commit: bool = False,
) -> GeneratedFile | None:
    """Index an assistant ``MessageFile`` backed by ``ToolFile``.

    Existing rows are enriched with the v1.0.21 source fields instead of duplicated.
    The caller owns the transaction unless ``commit`` is explicitly requested.
    """

    if message_file.transfer_method != FileTransferMethod.TOOL_FILE:
        return None
    if message_file.belongs_to not in (MessageFileBelongsTo.ASSISTANT, "assistant"):
        return None

    tool_file_id = _resolve_tool_file_id(message_file)
    if not tool_file_id:
        return None

    tool_file = session.get(ToolFile, tool_file_id)
    if not tool_file:
        return None
    if message is None:
        message = session.get(Message, message_file.message_id)

    candidate = _tool_file_candidate(
        tool_file,
        owner_user_id=message_file.created_by or tool_file.user_id,
        source_kind="message_file",
        source_app_id=str(message.app_id) if message else None,
        source_conversation_id=str(message.conversation_id) if message else tool_file.conversation_id,
        source_message_id=str(message_file.message_id),
        created_at=message_file.created_at,
    )
    generated_file, _ = register_generated_asset_candidate(session, candidate)
    if commit:
        session.commit()
        session.refresh(generated_file)
    return generated_file


def register_generated_file_from_tool_file(
    session: Session,
    tool_file: ToolFile,
    *,
    owner_user_id: str,
    source_kind: str = "tool_file",
    source_app_id: str | None = None,
    commit: bool = False,
) -> GeneratedFile:
    """Index a direct ``ToolFile`` artifact that has no ``MessageFile`` wrapper."""

    generated_file, _ = register_generated_asset_candidate(
        session,
        _tool_file_candidate(
            tool_file,
            owner_user_id=owner_user_id,
            source_kind=source_kind,
            source_app_id=source_app_id,
        ),
    )
    if commit:
        session.commit()
        session.refresh(generated_file)
    return generated_file


def register_generated_assets_from_workflow_run(
    session: Session,
    workflow_run: WorkflowRun,
) -> list[GeneratedFile]:
    """Index trusted final assets from one successful workflow run.

    The workflow persistence task calls this in the same transaction after flushing
    ``WorkflowRun``. Retries are safe because each final output has a deterministic
    tenant-scoped ``source_key``.
    """

    registered: list[GeneratedFile] = []
    candidates = [
        *extract_workflow_asset_candidates(workflow_run),
        *build_workflow_tool_file_candidates(session, workflow_run),
    ]
    for candidate in candidates:
        generated_file, _ = register_generated_asset_candidate(session, candidate)
        if candidate.source_kind == "workflow_video" and candidate.storage_type == "remote_url":
            try:
                persist_generated_video_asset(session, generated_file)
            except Exception:
                logger.exception(
                    "Failed to persist generated video locally: workflow_run_id=%s generated_file_id=%s",
                    workflow_run.id,
                    generated_file.id,
                )
        registered.append(generated_file)
    return registered


def persist_generated_video_asset(
    session: Session,
    generated_file: GeneratedFile,
    *,
    file_binary: bytes | None = None,
) -> bool:
    """Promote one trusted remote workflow video into durable Dify storage.

    The original provider URL is retained in metadata for audit, while every playback
    URL is generated from the local ``ToolFile`` after promotion. Repeated calls are
    idempotent and never overwrite an existing local copy.
    """

    if generated_file.source_kind != "workflow_video":
        raise ValueError("Only workflow video assets can be persisted by this service.")
    if generated_file.storage_type == "tool_file" and generated_file.tool_file_id:
        return False

    original_source_url = trusted_remote_asset_url(generated_file.source_url)
    if not original_source_url:
        raise FileNotFoundError("Generated video source is unavailable.")

    if file_binary is None:
        response = ssrf_proxy.get(original_source_url)
        response.raise_for_status()
        file_binary = response.content

    _validate_generated_video_binary(file_binary)
    extension = _asset_extension(generated_file) or ".mp4"
    storage_key = f"generated-videos/{generated_file.tenant_id}/{uuid4().hex}{extension}"
    storage.save(storage_key, file_binary)

    tool_file = ToolFile(
        user_id=str(generated_file.owner_user_id),
        tenant_id=str(generated_file.tenant_id),
        conversation_id=generated_file.source_conversation_id,
        file_key=storage_key,
        mimetype=generated_file.mime_type or "video/mp4",
        original_url=original_source_url,
        name=generated_file.name,
        size=len(file_binary),
    )
    session.add(tool_file)
    session.flush()

    metadata = dict(generated_file.asset_metadata or {})
    metadata.update(
        {
            "original_source_url": original_source_url,
            "local_persisted_at": datetime.now(UTC).isoformat(),
            "local_sha256": hashlib.sha256(file_binary).hexdigest(),
            "local_persistence_status": "persisted",
        }
    )
    metadata.pop("source_unavailable", None)
    metadata.pop("source_unavailable_at", None)
    generated_file.tool_file_id = str(tool_file.id)
    generated_file.storage_type = "tool_file"
    generated_file.source_url = None
    generated_file.size = len(file_binary)
    generated_file.asset_metadata = metadata
    session.add(generated_file)
    session.flush()
    return True


def mark_generated_video_source_unavailable(generated_file: GeneratedFile) -> bool:
    """Record a confirmed missing provider object without deleting its history row."""

    if generated_file.storage_type == "tool_file" and generated_file.tool_file_id:
        return False
    metadata = dict(generated_file.asset_metadata or {})
    if metadata.get("source_unavailable"):
        return False
    metadata.update(
        {
            "original_source_url": generated_file.source_url,
            "source_unavailable": True,
            "source_unavailable_at": datetime.now(UTC).isoformat(),
            "local_persistence_status": "source_missing",
        }
    )
    generated_file.asset_metadata = metadata
    return True


def _validate_generated_video_binary(file_binary: bytes) -> None:
    if not file_binary:
        raise ValueError("Generated video is empty.")
    if len(file_binary) > MAX_PERSISTED_VIDEO_BYTES:
        raise ValueError("Generated video exceeds the local persistence size limit.")
    if MP4_FILE_SIGNATURE not in file_binary[:32]:
        raise ValueError("Generated video is not a valid MP4 file.")


def build_workflow_tool_file_candidates(
    session: Session,
    workflow_run: WorkflowRun,
) -> list[GeneratedAssetCandidate]:
    """Resolve trusted native file objects from one workflow's final outputs."""

    candidates: list[GeneratedAssetCandidate] = []
    for tool_file_id in extract_workflow_tool_file_ids(workflow_run):
        tool_file = session.get(ToolFile, tool_file_id)
        if not tool_file:
            continue
        if str(tool_file.tenant_id) != str(workflow_run.tenant_id):
            logger.warning(
                "Ignored cross-tenant workflow ToolFile: workflow_run_id=%s tool_file_id=%s",
                workflow_run.id,
                tool_file_id,
            )
            continue
        if str(tool_file.user_id) != str(workflow_run.created_by):
            logger.warning(
                "Ignored cross-user workflow ToolFile: workflow_run_id=%s tool_file_id=%s",
                workflow_run.id,
                tool_file_id,
            )
            continue
        candidates.append(
            _tool_file_candidate(
                tool_file,
                owner_user_id=str(workflow_run.created_by),
                source_kind="workflow_tool_file",
                source_app_id=str(workflow_run.app_id),
                source_workflow_run_id=str(workflow_run.id),
                created_at=workflow_run.created_at,
            )
        )
    return candidates


def backfill_generated_files_for_user(session: Session, *, tenant_id: str, user_id: str, limit: int = 200) -> None:
    """Lazily index recent assistant ToolFiles for a console or external user."""

    rows = session.scalars(
        select(MessageFile)
        .join(ToolFile, ToolFile.id == MessageFile.upload_file_id)
        .outerjoin(GeneratedFile, GeneratedFile.tool_file_id == MessageFile.upload_file_id)
        .where(ToolFile.tenant_id == tenant_id)
        .where(MessageFile.created_by == user_id)
        .where(MessageFile.transfer_method == FileTransferMethod.TOOL_FILE)
        .where(MessageFile.belongs_to == MessageFileBelongsTo.ASSISTANT)
        .where(
            or_(
                GeneratedFile.id.is_(None),
                GeneratedFile.source_key.is_(None),
                GeneratedFile.owner_user_id != MessageFile.created_by,
            )
        )
        .order_by(MessageFile.created_at.desc())
        .limit(limit)
    ).all()
    changed = False
    for message_file in rows:
        if register_generated_file_from_message_file(session, message_file):
            changed = True
    if changed:
        session.commit()


def list_generated_files(
    session: Session,
    *,
    tenant_id: str,
    current_user: Account,
    page: int,
    limit: int,
    keyword: str | None = None,
    file_type: str | None = None,
    source_app_id: str | None = None,
    source_app_ids: str | None = None,
    owner_user_ids: str | None = None,
    source_kind: str | None = None,
    storage_type: str | None = None,
    created_after: datetime | None = None,
    created_before: datetime | None = None,
    include_all: bool = True,
    sort: str = "-created_at",
) -> dict[str, Any]:
    """List console-visible assets with role-aware tenant and owner scoping."""

    include_all = include_all and current_user.is_admin_or_owner
    filters: list[Any] = [GeneratedFile.tenant_id == tenant_id, GeneratedFile.deleted_at.is_(None)]
    if not include_all:
        filters.append(GeneratedFile.owner_user_id == current_user.id)
    filters.extend(
        _optional_asset_filters(
            keyword=keyword,
            file_type=file_type,
            source_kind=source_kind,
            storage_type=storage_type,
            created_after=created_after,
            created_before=created_before,
        )
    )
    facet_filters = list(filters)

    owner_ids = _split_filter_values(owner_user_ids)
    if owner_ids:
        filters.append(GeneratedFile.owner_user_id.in_(owner_ids))

    app_ids = _split_filter_values(source_app_ids)
    if source_app_id:
        app_ids.append(source_app_id)
    app_ids = list(dict.fromkeys(app_ids))
    if app_ids:
        explicit_app_ids = [app_id for app_id in app_ids if app_id != "unknown"]
        if "unknown" in app_ids and explicit_app_ids:
            filters.append(
                or_(GeneratedFile.source_app_id.in_(explicit_app_ids), GeneratedFile.source_app_id.is_(None))
            )
        elif "unknown" in app_ids:
            filters.append(GeneratedFile.source_app_id.is_(None))
        else:
            filters.append(GeneratedFile.source_app_id.in_(explicit_app_ids))

    return _execute_asset_list(
        session,
        filters=filters,
        facet_filters=facet_filters,
        page=page,
        limit=limit,
        sort=sort,
    )


def list_generated_files_for_end_user(
    session: Session,
    *,
    tenant_id: str,
    app_id: str,
    end_user_id: str,
    page: int,
    limit: int,
    keyword: str | None = None,
    file_type: str | None = None,
    source_kind: str | None = None,
    created_after: datetime | None = None,
    created_before: datetime | None = None,
    sort: str = "-created_at",
) -> dict[str, Any]:
    """List assets for exactly one Service API app and EndUser identity."""

    filters: list[Any] = [
        GeneratedFile.tenant_id == tenant_id,
        GeneratedFile.source_app_id == app_id,
        GeneratedFile.owner_user_id == end_user_id,
        GeneratedFile.deleted_at.is_(None),
        *_optional_asset_filters(
            keyword=keyword,
            file_type=file_type,
            source_kind=source_kind,
            created_after=created_after,
            created_before=created_before,
        ),
    ]
    return _execute_asset_list(session, filters=filters, facet_filters=filters, page=page, limit=limit, sort=sort)


def get_generated_file_for_user(
    session: Session, *, generated_file_id: str, tenant_id: str, current_user: Account
) -> GeneratedFile | None:
    """Return one console-visible asset without leaking out-of-scope existence."""

    filters = [
        GeneratedFile.id == generated_file_id,
        GeneratedFile.tenant_id == tenant_id,
        GeneratedFile.deleted_at.is_(None),
    ]
    if not current_user.is_admin_or_owner:
        filters.append(GeneratedFile.owner_user_id == current_user.id)
    return session.scalar(select(GeneratedFile).where(*filters).limit(1))


def get_generated_file_for_end_user(
    session: Session,
    *,
    generated_file_id: str,
    tenant_id: str,
    app_id: str,
    end_user_id: str,
) -> GeneratedFile | None:
    """Return one asset only when tenant, app, and EndUser all match."""

    return session.scalar(
        select(GeneratedFile)
        .where(
            GeneratedFile.id == generated_file_id,
            GeneratedFile.tenant_id == tenant_id,
            GeneratedFile.source_app_id == app_id,
            GeneratedFile.owner_user_id == end_user_id,
            GeneratedFile.deleted_at.is_(None),
        )
        .limit(1)
    )


def _generated_asset_preview_fields(generated_file: GeneratedFile, extension: str) -> dict[str, Any]:
    return {
        "id": str(generated_file.id),
        "name": generated_file.name,
        "mime_type": generated_file.mime_type,
        "file_type": generated_file.file_type,
        "extension": extension,
        "size": generated_file.size,
        "created_at": _to_timestamp(generated_file.created_at),
        "source_app_id": str(generated_file.source_app_id) if generated_file.source_app_id else None,
        "source_app_name": None,
        "source_conversation_id": str(generated_file.source_conversation_id)
        if generated_file.source_conversation_id
        else None,
        "source_message_id": str(generated_file.source_message_id) if generated_file.source_message_id else None,
        "source_workflow_run_id": str(generated_file.source_workflow_run_id)
        if generated_file.source_workflow_run_id
        else None,
        "owner_user_id": str(generated_file.owner_user_id),
        "owner_name": None,
        "storage_type": generated_file.storage_type,
        "source_kind": generated_file.source_kind,
        "source_url": generated_file.source_url,
        "thumbnail_url": generated_file.thumbnail_url,
        "asset_metadata": generated_file.asset_metadata or {},
    }


def build_generated_file_preview_config(generated_file: GeneratedFile) -> dict[str, Any]:
    """Build preview metadata without fetching remote content."""

    extension = _asset_extension(generated_file)
    original_file_type = extension.lstrip(".").lower()
    fields = _generated_asset_preview_fields(generated_file, original_file_type)
    if generated_file.storage_type == "remote_url":
        source_url = trusted_remote_asset_url(generated_file.source_url)
        preview_kind = "native" if source_url and original_file_type in NATIVE_PREVIEW_TYPES else "unavailable"
        return {
            **fields,
            "mode": "remote",
            "original_file_type": original_file_type,
            "preview_kind": preview_kind,
            "preview_url": source_url or "",
            "download_url": source_url or "",
        }

    if not generated_file.tool_file_id:
        return _unavailable_preview(fields, original_file_type)
    signed_url = sign_tool_file(generated_file.tool_file_id, extension)
    if original_file_type in OFFICE_PREVIEW_TYPES:
        return {
            **fields,
            "mode": "native",
            "original_file_type": original_file_type,
            "preview_kind": "converted_pdf",
            "preview_url": f"/generated-assets/{generated_file.id}/converted-preview",
            "download_url": _as_attachment_url(signed_url),
        }
    preview_kind = "native" if original_file_type in NATIVE_PREVIEW_TYPES else "unsupported"
    return {
        **fields,
        "mode": "native",
        "original_file_type": original_file_type,
        "preview_kind": preview_kind,
        "preview_url": signed_url if preview_kind == "native" else "",
        "download_url": _as_attachment_url(signed_url),
    }


def build_generated_file_download_url(generated_file: GeneratedFile) -> str:
    """Return a trusted remote URL or signed local ToolFile URL."""

    if generated_file.storage_type == "remote_url":
        source_url = trusted_remote_asset_url(generated_file.source_url)
        if not source_url:
            raise FileNotFoundError("Generated asset source is unavailable.")
        return source_url
    if not generated_file.tool_file_id:
        raise FileNotFoundError("Generated asset source is unavailable.")
    return _as_attachment_url(sign_tool_file(generated_file.tool_file_id, _asset_extension(generated_file)))


def convert_generated_file_to_pdf(session: Session, generated_file: GeneratedFile) -> Path:
    """Convert a local Office ToolFile to a cached PDF preview."""

    if generated_file.storage_type != "tool_file" or not generated_file.tool_file_id:
        raise ValueError("Remote generated assets do not support converted preview.")
    file_type = _asset_extension(generated_file).lstrip(".").lower()
    if file_type not in OFFICE_PREVIEW_TYPES:
        raise ValueError("Generated file type does not support converted preview.")

    tool_file = session.get(ToolFile, generated_file.tool_file_id)
    if not tool_file:
        raise FileNotFoundError("Generated file source not found.")
    soffice = shutil.which("soffice") or shutil.which("libreoffice")
    if not soffice:
        raise RuntimeError("Generated file preview converter is not installed.")

    output_path = _generated_file_preview_pdf_cache_path(generated_file, tool_file)
    if output_path.exists() and output_path.stat().st_size > 0:
        return output_path

    GENERATED_FILE_PREVIEW_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="dify-generated-file-preview-") as temp_dir:
        temp_path = Path(temp_dir)
        source_path = temp_path / f"source.{file_type or 'bin'}"
        source_path.write_bytes(storage.load_once(tool_file.file_key))
        profile_dir = temp_path / "libreoffice-profile"
        output_dir = temp_path / "out"
        output_dir.mkdir()
        result = subprocess.run(
            [
                soffice,
                "--headless",
                "--nologo",
                "--nofirststartwizard",
                f"-env:UserInstallation=file://{profile_dir}",
                "--convert-to",
                "pdf",
                "--outdir",
                str(output_dir),
                str(source_path),
            ],
            capture_output=True,
            text=True,
            timeout=180,
            check=False,
        )
        converted_files = list(output_dir.glob("*.pdf"))
        if result.returncode != 0 or not converted_files:
            logger.warning(
                "Generated file PDF preview conversion failed: generated_file_id=%s "
                "tool_file_id=%s returncode=%s stdout=%s stderr=%s",
                generated_file.id,
                tool_file.id,
                result.returncode,
                result.stdout[-1000:],
                result.stderr[-1000:],
            )
            raise RuntimeError("Generated file preview conversion failed.")
        temp_cache_path = output_path.with_suffix(".tmp")
        shutil.copyfile(converted_files[0], temp_cache_path)
        os.replace(temp_cache_path, output_path)
    return output_path


def soft_delete_generated_file(session: Session, generated_file: GeneratedFile) -> None:
    """Soft-delete an asset index row without deleting local or remote content."""

    generated_file.deleted_at = datetime.utcnow()
    session.add(generated_file)
    session.commit()


def serialize_generated_asset(
    generated_file: GeneratedFile, *, source_app_name: str | None, owner_name: str | None
) -> dict[str, Any]:
    """Serialize the stable console and Service API asset representation."""

    config = build_generated_file_preview_config(generated_file)
    return {
        "id": str(generated_file.id),
        "name": generated_file.name,
        "mime_type": generated_file.mime_type,
        "file_type": generated_file.file_type,
        "extension": config["original_file_type"],
        "original_file_type": config["original_file_type"],
        "size": generated_file.size,
        "created_at": _to_timestamp(generated_file.created_at),
        "source_app_id": str(generated_file.source_app_id) if generated_file.source_app_id else None,
        "source_app_name": source_app_name,
        "source_conversation_id": str(generated_file.source_conversation_id)
        if generated_file.source_conversation_id
        else None,
        "source_message_id": str(generated_file.source_message_id) if generated_file.source_message_id else None,
        "source_workflow_run_id": str(generated_file.source_workflow_run_id)
        if generated_file.source_workflow_run_id
        else None,
        "owner_user_id": str(generated_file.owner_user_id),
        "owner_name": owner_name,
        "storage_type": generated_file.storage_type,
        "source_kind": generated_file.source_kind,
        "source_url": generated_file.source_url,
        "thumbnail_url": generated_file.thumbnail_url,
        "asset_metadata": generated_file.asset_metadata or {},
        "preview_kind": config["preview_kind"],
        "mode": config["mode"],
        "preview_url": config["preview_url"],
        "download_url": config["download_url"],
    }


def _execute_asset_list(
    session: Session,
    *,
    filters: list[Any],
    facet_filters: list[Any],
    page: int,
    limit: int,
    sort: str,
) -> dict[str, Any]:
    order_column = GeneratedFile.created_at.asc() if sort == "created_at" else GeneratedFile.created_at.desc()
    total = session.scalar(select(func.count()).select_from(GeneratedFile).where(*filters)) or 0
    total_size = (
        session.scalar(
            select(func.coalesce(func.sum(case((GeneratedFile.size > 0, GeneratedFile.size), else_=0)), 0)).where(
                *filters
            )
        )
        or 0
    )
    type_counts = dict(
        session.execute(select(GeneratedFile.file_type, func.count()).where(*filters).group_by(GeneratedFile.file_type))
        .tuples()
        .all()
    )
    rows = session.execute(
        select(GeneratedFile, App.name, Account.name, EndUser.session_id, EndUser.type, EndUser.name)
        .outerjoin(App, App.id == GeneratedFile.source_app_id)
        .outerjoin(Account, Account.id == GeneratedFile.owner_user_id)
        .outerjoin(EndUser, EndUser.id == GeneratedFile.owner_user_id)
        .where(*filters)
        .order_by(order_column, GeneratedFile.id.desc())
        .offset((page - 1) * limit)
        .limit(limit)
    ).all()
    return {
        "data": [
            serialize_generated_asset(
                row[0],
                source_app_name=row[1],
                owner_name=_owner_display_name(
                    owner_id=str(row[0].owner_user_id),
                    account_name=row[2],
                    end_user_session_id=row[3],
                    end_user_type=row[4],
                    end_user_name=row[5],
                ),
            )
            for row in rows
        ],
        "page": page,
        "limit": limit,
        "total": total,
        "has_more": page * limit < total,
        "facets": _build_generated_file_facets(session, facet_filters),
        "stats": {"total": total, "total_size": int(total_size), "by_type": type_counts},
    }


def _optional_asset_filters(
    *,
    keyword: str | None,
    file_type: str | None,
    source_kind: str | None,
    storage_type: str | None = None,
    created_after: datetime | None,
    created_before: datetime | None,
) -> list[Any]:
    filters: list[Any] = []
    if keyword:
        filters.append(GeneratedFile.name.ilike(f"%{keyword.strip()}%"))
    if file_type and file_type != "all":
        filters.append(GeneratedFile.file_type == file_type)
    if source_kind and source_kind != "all":
        filters.append(GeneratedFile.source_kind == source_kind)
    if storage_type and storage_type != "all":
        filters.append(GeneratedFile.storage_type == storage_type)
    if created_after:
        filters.append(GeneratedFile.created_at >= created_after)
    if created_before:
        filters.append(GeneratedFile.created_at < created_before)
    return filters


def register_generated_asset_candidate(
    session: Session, candidate: GeneratedAssetCandidate
) -> tuple[GeneratedFile, bool]:
    existing = _find_existing_asset(session, candidate)
    if existing:
        _enrich_existing_asset(existing, candidate)
        session.add(existing)
        session.flush()
        return existing, False

    try:
        with session.begin_nested():
            generated_file = GeneratedFile(
                tenant_id=candidate.tenant_id,
                owner_user_id=candidate.owner_user_id,
                tool_file_id=candidate.tool_file_id,
                storage_type=candidate.storage_type,
                source_url=candidate.source_url,
                thumbnail_url=candidate.thumbnail_url,
                source_app_id=candidate.source_app_id,
                source_conversation_id=candidate.source_conversation_id,
                source_message_id=candidate.source_message_id,
                source_workflow_run_id=candidate.source_workflow_run_id,
                source_kind=candidate.source_kind,
                source_key=candidate.source_key,
                asset_metadata=candidate.asset_metadata,
                name=candidate.name,
                mime_type=candidate.mime_type,
                file_type=candidate.file_type,
                size=candidate.size,
            )
            if candidate.created_at is not None:
                generated_file.created_at = candidate.created_at
            session.add(generated_file)
            session.flush()
    except IntegrityError:
        existing = _find_existing_asset(session, candidate)
        if existing is None:
            raise
        _enrich_existing_asset(existing, candidate)
        session.add(existing)
        session.flush()
        return existing, False
    return generated_file, True


def _find_existing_asset(session: Session, candidate: GeneratedAssetCandidate) -> GeneratedFile | None:
    identity_filters: list[Any] = [GeneratedFile.source_key == candidate.source_key]
    if candidate.tool_file_id:
        identity_filters.append(GeneratedFile.tool_file_id == candidate.tool_file_id)
    return session.scalar(
        select(GeneratedFile).where(GeneratedFile.tenant_id == candidate.tenant_id, or_(*identity_filters)).limit(1)
    )


def _enrich_existing_asset(generated_file: GeneratedFile, candidate: GeneratedAssetCandidate) -> None:
    # An assistant MessageFile is the authoritative ownership link for a ToolFile.
    if (
        candidate.source_kind == "message_file"
        and candidate.source_message_id
        and candidate.tool_file_id
        and str(generated_file.tool_file_id) == candidate.tool_file_id
    ):
        generated_file.owner_user_id = candidate.owner_user_id
    durable_video = (
        generated_file.source_kind == "workflow_video"
        and generated_file.storage_type == "tool_file"
        and generated_file.tool_file_id is not None
    )
    if not durable_video:
        generated_file.storage_type = candidate.storage_type
    generated_file.source_kind = candidate.source_kind
    generated_file.source_key = generated_file.source_key or candidate.source_key
    if candidate.storage_type == "remote_url" and not durable_video:
        generated_file.source_url = candidate.source_url or generated_file.source_url
        generated_file.thumbnail_url = candidate.thumbnail_url or generated_file.thumbnail_url
    else:
        generated_file.source_url = generated_file.source_url or candidate.source_url
        generated_file.thumbnail_url = generated_file.thumbnail_url or candidate.thumbnail_url
    generated_file.source_app_id = generated_file.source_app_id or candidate.source_app_id
    generated_file.source_conversation_id = generated_file.source_conversation_id or candidate.source_conversation_id
    generated_file.source_message_id = generated_file.source_message_id or candidate.source_message_id
    generated_file.source_workflow_run_id = generated_file.source_workflow_run_id or candidate.source_workflow_run_id
    if durable_video and candidate.asset_metadata:
        metadata = dict(generated_file.asset_metadata or {})
        metadata.update(candidate.asset_metadata)
        generated_file.asset_metadata = metadata
        generated_file.source_url = None
    elif candidate.asset_metadata and (candidate.storage_type == "remote_url" or not generated_file.asset_metadata):
        generated_file.asset_metadata = candidate.asset_metadata


def _tool_file_candidate(
    tool_file: ToolFile,
    *,
    owner_user_id: str,
    source_kind: str,
    source_app_id: str | None = None,
    source_conversation_id: str | None = None,
    source_message_id: str | None = None,
    source_workflow_run_id: str | None = None,
    created_at: datetime | None = None,
) -> GeneratedAssetCandidate:
    return GeneratedAssetCandidate(
        tenant_id=str(tool_file.tenant_id),
        owner_user_id=str(owner_user_id),
        tool_file_id=str(tool_file.id),
        storage_type="tool_file",
        source_kind=source_kind,
        source_key=f"tool-file:{tool_file.id}",
        source_app_id=source_app_id,
        source_conversation_id=source_conversation_id or tool_file.conversation_id,
        source_message_id=source_message_id,
        source_workflow_run_id=source_workflow_run_id,
        name=tool_file.name or _fallback_filename(tool_file),
        mime_type=tool_file.mimetype or "application/octet-stream",
        file_type=classify_file_type(tool_file.mimetype, tool_file.name),
        size=tool_file.size,
        created_at=created_at,
    )


def generated_asset_exists(
    session: Session,
    *,
    tool_file_id: str | None = None,
    source_key: str | None = None,
    tenant_id: str | None = None,
) -> bool:
    filters: list[Any] = []
    if tool_file_id:
        filters.append(GeneratedFile.tool_file_id == tool_file_id)
    if source_key:
        filters.append(GeneratedFile.source_key == source_key)
    if not filters:
        return False
    stmt = select(GeneratedFile.id).where(or_(*filters))
    if tenant_id:
        stmt = stmt.where(GeneratedFile.tenant_id == tenant_id)
    return session.scalar(stmt.limit(1)) is not None


def _resolve_tool_file_id(message_file: MessageFile) -> str | None:
    if message_file.upload_file_id:
        return str(message_file.upload_file_id)
    if not message_file.url:
        return None
    file_part = message_file.url.split("/")[-1].split("?")[0]
    return file_part.rsplit(".", 1)[0] if "." in file_part else file_part


def _asset_extension(generated_file: GeneratedFile) -> str:
    if generated_file.name and "." in generated_file.name:
        return _extension_from_name_or_mime(generated_file.name, generated_file.mime_type)
    if generated_file.source_url:
        return _extension_from_url(generated_file.source_url, default=".bin")
    return _extension_from_name_or_mime(generated_file.name, generated_file.mime_type)


def _extension_from_name_or_mime(name: str | None, mime_type: str | None) -> str:
    if name and "." in name:
        suffix = f".{name.rsplit('.', 1)[1].lower()}"
        if 1 < len(suffix) <= 12:
            return suffix
    return guess_extension(mime_type or "") or ".bin"


def _extension_from_url(url: str, *, default: str) -> str:
    suffix = Path(urlsplit(url).path).suffix.lower()
    return suffix if 1 < len(suffix) <= 12 else default


def _fallback_filename(tool_file: ToolFile) -> str:
    return f"{tool_file.id}{_extension_from_name_or_mime(tool_file.name, tool_file.mimetype)}"


def _as_attachment_url(url: str) -> str:
    separator = "&" if "?" in url else "?"
    return f"{url}{separator}as_attachment=true"


def _generated_file_preview_pdf_cache_path(generated_file: GeneratedFile, tool_file: ToolFile) -> Path:
    cache_key = hashlib.sha256(
        f"generated-file-preview-pdf-v1:{generated_file.id}:{tool_file.id}:{tool_file.size}".encode()
    ).hexdigest()
    return GENERATED_FILE_PREVIEW_CACHE_DIR / f"{cache_key}.pdf"


def _to_timestamp(value: datetime | None) -> int | None:
    return int(value.timestamp()) if value else None


def _split_filter_values(value: str | None) -> list[str]:
    if not value:
        return []
    return [item.strip() for item in value.split(",") if item.strip()]


def _build_generated_file_facets(session: Session, filters: list[Any]) -> dict[str, list[dict[str, Any]]]:
    account_rows = session.execute(
        select(
            GeneratedFile.owner_user_id,
            Account.name,
            EndUser.session_id,
            EndUser.type,
            EndUser.name,
            func.count(GeneratedFile.id),
        )
        .outerjoin(Account, Account.id == GeneratedFile.owner_user_id)
        .outerjoin(EndUser, EndUser.id == GeneratedFile.owner_user_id)
        .where(*filters)
        .group_by(GeneratedFile.owner_user_id, Account.name, EndUser.session_id, EndUser.type, EndUser.name)
        .order_by(func.count(GeneratedFile.id).desc(), Account.name.asc(), EndUser.session_id.asc())
    ).all()
    app_rows = session.execute(
        select(GeneratedFile.source_app_id, App.name, func.count(GeneratedFile.id))
        .outerjoin(App, App.id == GeneratedFile.source_app_id)
        .where(*filters)
        .group_by(GeneratedFile.source_app_id, App.name)
        .order_by(func.count(GeneratedFile.id).desc(), App.name.asc())
    ).all()
    return {
        "accounts": [
            {
                "id": str(owner_id),
                "name": _owner_display_name(
                    owner_id=str(owner_id),
                    account_name=owner_name,
                    end_user_session_id=end_user_session_id,
                    end_user_type=end_user_type,
                    end_user_name=end_user_name,
                ),
                "count": count,
            }
            for owner_id, owner_name, end_user_session_id, end_user_type, end_user_name, count in account_rows
            if owner_id
        ],
        "apps": [
            {"id": str(app_id) if app_id else "unknown", "name": app_name or "未知应用", "count": count}
            for app_id, app_name, count in app_rows
        ],
        "file_types": _simple_facet(session, GeneratedFile.file_type, filters),
        "source_kinds": _simple_facet(session, GeneratedFile.source_kind, filters),
        "storage_types": _simple_facet(session, GeneratedFile.storage_type, filters),
    }


def _simple_facet(session: Session, column: Any, filters: list[Any]) -> list[dict[str, Any]]:
    rows = session.execute(
        select(column, func.count(GeneratedFile.id))
        .where(*filters)
        .group_by(column)
        .order_by(func.count(GeneratedFile.id).desc())
    ).all()
    return [{"id": value, "name": value, "count": count} for value, count in rows if value]


def _owner_display_name(
    *,
    owner_id: str,
    account_name: str | None,
    end_user_session_id: str | None,
    end_user_type: str | None,
    end_user_name: str | None,
) -> str:
    if account_name:
        return account_name
    if end_user_name:
        return end_user_name
    if end_user_session_id:
        if end_user_type == "service-api":
            namespace, separator, external_id = end_user_session_id.partition(":")
            if separator and namespace and external_id:
                return f"{namespace} · {_short_identity(external_id)}"
            return f"Service API 用户 · {_short_identity(end_user_session_id)}"
        if end_user_type == "web-app":
            return f"WebApp 用户 · {_short_identity(end_user_session_id)}"
        return f"外部用户 · {_short_identity(end_user_session_id)}"
    return f"外部用户 · {_short_identity(owner_id)}"


def _short_identity(value: str) -> str:
    return f"{value[:4]}...{value[-4:]}" if len(value) > 12 else value


def _unavailable_preview(fields: dict[str, Any], original_file_type: str) -> dict[str, Any]:
    return {
        **fields,
        "mode": "unavailable",
        "original_file_type": original_file_type,
        "preview_kind": "unavailable",
        "preview_url": "",
        "download_url": "",
    }
