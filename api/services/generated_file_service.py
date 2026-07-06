from __future__ import annotations

import hashlib
import logging
import os
import shutil
import subprocess
import tempfile
from datetime import datetime
from mimetypes import guess_extension
from pathlib import Path
from typing import Any

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from core.tools.signature import sign_tool_file
from extensions.ext_storage import storage
from graphon.file import FileTransferMethod
from models.account import Account
from models.enums import MessageFileBelongsTo
from models.model import App, EndUser, Message, MessageFile
from models.tools import GeneratedFile, ToolFile

logger = logging.getLogger(__name__)

IMAGE_TYPES = {"bmp", "gif", "jpeg", "jpg", "png", "svg", "webp"}
TEXT_TYPES = {"csv", "json", "log", "md", "txt", "xml", "yaml", "yml"}
OFFICE_PREVIEW_TYPES = {"doc", "docx", "ppt", "pptx", "xls", "xlsx"}
NATIVE_PREVIEW_TYPES = {*IMAGE_TYPES, *TEXT_TYPES, "pdf"}
GENERATED_FILE_PREVIEW_CACHE_DIR = Path(os.getenv("DOCUMENT_PREVIEW_CACHE_DIR", "/tmp/dify-document-previews"))


def classify_file_type(mime_type: str, name: str = "") -> str:
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
    if message_file.transfer_method != FileTransferMethod.TOOL_FILE:
        return None
    if message_file.belongs_to not in (MessageFileBelongsTo.ASSISTANT, "assistant"):
        return None

    tool_file_id = _resolve_tool_file_id(message_file)
    if not tool_file_id:
        return None

    existing = session.scalar(select(GeneratedFile).where(GeneratedFile.tool_file_id == tool_file_id).limit(1))
    if existing:
        return existing

    tool_file = session.get(ToolFile, tool_file_id)
    if not tool_file:
        return None

    if message is None:
        message = session.get(Message, message_file.message_id)

    generated_file = GeneratedFile(
        tenant_id=tool_file.tenant_id,
        owner_user_id=message_file.created_by or tool_file.user_id,
        tool_file_id=str(tool_file.id),
        source_app_id=str(message.app_id) if message else None,
        source_conversation_id=str(message.conversation_id) if message else tool_file.conversation_id,
        source_message_id=str(message_file.message_id),
        name=tool_file.name or _fallback_filename(tool_file),
        mime_type=tool_file.mimetype or "application/octet-stream",
        file_type=classify_file_type(tool_file.mimetype, tool_file.name),
        size=tool_file.size,
    )
    session.add(generated_file)
    session.flush()
    if commit:
        session.commit()
        session.refresh(generated_file)
    return generated_file


def backfill_generated_files_for_user(session: Session, *, tenant_id: str, user_id: str, limit: int = 200) -> None:
    rows = session.scalars(
        select(MessageFile)
        .join(ToolFile, ToolFile.id == MessageFile.upload_file_id)
        .where(ToolFile.tenant_id == tenant_id)
        .where(MessageFile.created_by == user_id)
        .where(MessageFile.transfer_method == FileTransferMethod.TOOL_FILE)
        .where(MessageFile.belongs_to == MessageFileBelongsTo.ASSISTANT)
        .where(~select(GeneratedFile.id).where(GeneratedFile.tool_file_id == MessageFile.upload_file_id).exists())
        .order_by(MessageFile.created_at.desc())
        .limit(limit)
    ).all()
    for message_file in rows:
        register_generated_file_from_message_file(session, message_file)
    if rows:
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
    include_all: bool = False,
    sort: str = "-created_at",
) -> dict[str, Any]:
    include_all = include_all and current_user.is_admin_or_owner
    filters = [GeneratedFile.tenant_id == tenant_id, GeneratedFile.deleted_at.is_(None)]
    if not include_all:
        filters.append(GeneratedFile.owner_user_id == current_user.id)
    if keyword:
        filters.append(GeneratedFile.name.ilike(f"%{keyword.strip()}%"))
    if file_type and file_type != "all":
        filters.append(GeneratedFile.file_type == file_type)

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
                or_(
                    GeneratedFile.source_app_id.in_(explicit_app_ids),
                    GeneratedFile.source_app_id.is_(None),
                )
            )
        elif "unknown" in app_ids:
            filters.append(GeneratedFile.source_app_id.is_(None))
        else:
            filters.append(GeneratedFile.source_app_id.in_(explicit_app_ids))

    order_column = GeneratedFile.created_at.asc() if sort == "created_at" else GeneratedFile.created_at.desc()
    total = session.scalar(select(func.count()).select_from(GeneratedFile).where(*filters)) or 0
    total_size = session.scalar(select(func.coalesce(func.sum(GeneratedFile.size), 0)).where(*filters)) or 0
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
        .order_by(order_column)
        .offset((page - 1) * limit)
        .limit(limit)
    ).all()

    return {
        "data": [
            _serialize_generated_file(
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
        "stats": {
            "total": total,
            "total_size": int(total_size),
            "by_type": type_counts,
        },
    }


def get_generated_file_for_user(
    session: Session, *, generated_file_id: str, tenant_id: str, current_user: Account
) -> GeneratedFile | None:
    filters = [
        GeneratedFile.id == generated_file_id,
        GeneratedFile.tenant_id == tenant_id,
        GeneratedFile.deleted_at.is_(None),
    ]
    if not current_user.is_admin_or_owner:
        filters.append(GeneratedFile.owner_user_id == current_user.id)
    return session.scalar(select(GeneratedFile).where(*filters).limit(1))


def build_generated_file_preview_config(generated_file: GeneratedFile) -> dict[str, Any]:
    extension = _extension_from_name_or_mime(generated_file.name, generated_file.mime_type)
    signed_url = sign_tool_file(generated_file.tool_file_id, extension)
    file_type = extension.lstrip(".").lower()
    if file_type in OFFICE_PREVIEW_TYPES:
        return {
            "mode": "native",
            "file_type": "pdf",
            "original_file_type": file_type,
            "preview_kind": "converted_pdf",
            "name": generated_file.name,
            "preview_url": f"/generated-files/{generated_file.id}/converted-preview",
            "download_url": _as_attachment_url(signed_url),
        }

    preview_kind = "native" if file_type in NATIVE_PREVIEW_TYPES else "unsupported"
    return {
        "mode": "native",
        "file_type": file_type,
        "preview_kind": preview_kind,
        "name": generated_file.name,
        "preview_url": signed_url if preview_kind == "native" else "",
        "download_url": _as_attachment_url(signed_url),
    }


def build_generated_file_download_url(generated_file: GeneratedFile) -> str:
    extension = _extension_from_name_or_mime(generated_file.name, generated_file.mime_type)
    return _as_attachment_url(sign_tool_file(generated_file.tool_file_id, extension))


def convert_generated_file_to_pdf(session: Session, generated_file: GeneratedFile) -> Path:
    file_type = _extension_from_name_or_mime(generated_file.name, generated_file.mime_type).lstrip(".").lower()
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
    source_suffix = f".{file_type or 'bin'}"

    with tempfile.TemporaryDirectory(prefix="dify-generated-file-preview-") as temp_dir:
        temp_path = Path(temp_dir)
        source_path = temp_path / f"source{source_suffix}"
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

        temp_output = converted_files[0]
        temp_cache_path = output_path.with_suffix(".tmp")
        shutil.copyfile(temp_output, temp_cache_path)
        os.replace(temp_cache_path, output_path)

    return output_path


def soft_delete_generated_file(session: Session, generated_file: GeneratedFile) -> None:
    generated_file.deleted_at = datetime.utcnow()
    session.add(generated_file)
    session.commit()


def _serialize_generated_file(
    generated_file: GeneratedFile, *, source_app_name: str | None, owner_name: str | None
) -> dict[str, Any]:
    config = build_generated_file_preview_config(generated_file)
    return {
        "id": str(generated_file.id),
        "name": generated_file.name,
        "mime_type": generated_file.mime_type,
        "file_type": generated_file.file_type,
        "extension": config["file_type"],
        "size": generated_file.size,
        "created_at": _to_timestamp(generated_file.created_at),
        "source_app_id": str(generated_file.source_app_id) if generated_file.source_app_id else None,
        "source_app_name": source_app_name,
        "source_conversation_id": str(generated_file.source_conversation_id)
        if generated_file.source_conversation_id
        else None,
        "source_message_id": str(generated_file.source_message_id) if generated_file.source_message_id else None,
        "owner_user_id": str(generated_file.owner_user_id),
        "owner_name": owner_name,
        "preview_kind": config["preview_kind"],
        "preview_url": config["preview_url"],
        "download_url": config["download_url"],
    }


def _resolve_tool_file_id(message_file: MessageFile) -> str | None:
    if message_file.upload_file_id:
        return str(message_file.upload_file_id)
    if not message_file.url:
        return None
    file_part = message_file.url.split("/")[-1].split("?")[0]
    return file_part.rsplit(".", 1)[0] if "." in file_part else file_part


def _extension_from_name_or_mime(name: str | None, mime_type: str | None) -> str:
    if name and "." in name:
        suffix = f".{name.rsplit('.', 1)[1].lower()}"
        if 1 < len(suffix) <= 12:
            return suffix
    return guess_extension(mime_type or "") or ".bin"


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
        select(
            GeneratedFile.source_app_id,
            App.name,
            func.count(GeneratedFile.id),
        )
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
            {
                "id": str(app_id) if app_id else "unknown",
                "name": app_name or "未知应用",
                "count": count,
            }
            for app_id, app_name, count in app_rows
        ],
    }


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
        suffix = _short_identity(end_user_session_id)
        if end_user_type == "service-api":
            return f"飞书/Hermes 用户 · {suffix}"
        if end_user_type == "web-app":
            return f"WebApp 用户 · {suffix}"
        return f"外部用户 · {suffix}"
    return f"外部用户 · {_short_identity(owner_id)}"


def _short_identity(value: str) -> str:
    return value[:8] if len(value) > 8 else value
