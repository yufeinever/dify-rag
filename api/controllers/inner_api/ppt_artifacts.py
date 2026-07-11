from __future__ import annotations

import hmac
import logging
from io import BytesIO
from pathlib import PurePath
from zipfile import BadZipFile, ZipFile

from flask import request
from flask_restx import Resource
from sqlalchemy import select
from werkzeug.exceptions import (
    BadRequest,
    Forbidden,
    NotFound,
    RequestEntityTooLarge,
    UnsupportedMediaType,
)

from configs import dify_config
from controllers.console.wraps import setup_required
from controllers.inner_api import inner_api_ns
from core.tools.signature import sign_tool_file
from core.tools.tool_file_manager import ToolFileManager
from extensions.ext_database import db
from models import Account, Tenant, TenantAccountJoin
from services.generated_file_service import register_generated_file_from_tool_file

logger = logging.getLogger(__name__)

PPTX_MIME_TYPE = "application/vnd.openxmlformats-officedocument.presentationml.presentation"
PPTX_MAX_BYTES = 30 * 1024 * 1024
PPTX_MAX_UNCOMPRESSED_BYTES = 200 * 1024 * 1024
PPTX_MAX_ENTRIES = 2_000
PPTX_REQUIRED_ENTRIES = {"[Content_Types].xml", "ppt/presentation.xml"}


def validate_pptx_upload(filename: str, content: bytes) -> str:
    if not filename or PurePath(filename).name != filename or any(char in filename for char in ("/", "\\")):
        raise BadRequest("Invalid filename.")
    if not filename.lower().endswith(".pptx"):
        raise UnsupportedMediaType("Only .pptx files are accepted.")
    if not content:
        raise BadRequest("The PPTX file is empty.")
    if len(content) > PPTX_MAX_BYTES:
        raise RequestEntityTooLarge("The PPTX file exceeds the 30 MiB limit.")

    try:
        with ZipFile(BytesIO(content)) as archive:
            entries = archive.infolist()
            names = {entry.filename for entry in entries}
            if not PPTX_REQUIRED_ENTRIES.issubset(names):
                raise BadRequest("The file is not a valid PPTX package.")
            if not any(name.startswith("ppt/slides/slide") and name.endswith(".xml") for name in names):
                raise BadRequest("The PPTX package contains no slides.")
            if len(entries) > PPTX_MAX_ENTRIES:
                raise BadRequest("The PPTX package contains too many entries.")
            if sum(entry.file_size for entry in entries) > PPTX_MAX_UNCOMPRESSED_BYTES:
                raise BadRequest("The PPTX package expands beyond the allowed size.")
            if archive.testzip() is not None:
                raise BadRequest("The PPTX package is corrupted.")
    except BadZipFile as exc:
        raise BadRequest("The file is not a valid PPTX package.") from exc

    return filename


def _require_artifact_api_key() -> None:
    configured_key = dify_config.PPT_ARTIFACT_API_KEY
    authorization = request.headers.get("Authorization", "")
    supplied_key = authorization.removeprefix("Bearer ").strip() if authorization.startswith("Bearer ") else ""
    if not configured_key or not supplied_key or not hmac.compare_digest(configured_key, supplied_key):
        raise NotFound()


@inner_api_ns.route("/model-artifacts/pptx")
class ModelPptxArtifactUploadApi(Resource):
    @setup_required
    def post(self):
        _require_artifact_api_key()

        tenant_id = request.form.get("tenant_id", "").strip()
        user_id = request.form.get("user_id", "").strip()
        upload = request.files.get("file")
        if not tenant_id or not user_id or upload is None:
            raise BadRequest("tenant_id, user_id and file are required.")

        tenant = db.session.get(Tenant, tenant_id)
        account = db.session.get(Account, user_id)
        membership = db.session.scalar(
            select(TenantAccountJoin.id).where(
                TenantAccountJoin.tenant_id == tenant_id,
                TenantAccountJoin.account_id == user_id,
            )
        )
        if tenant is None or account is None or membership is None:
            raise Forbidden("The configured artifact owner does not belong to the tenant.")

        filename = upload.filename or ""
        content = upload.stream.read(PPTX_MAX_BYTES + 1)
        filename = validate_pptx_upload(filename, content)

        tool_file = ToolFileManager().create_file_by_raw(
            user_id=user_id,
            tenant_id=tenant_id,
            conversation_id=None,
            file_binary=content,
            mimetype=PPTX_MIME_TYPE,
            filename=filename,
        )
        try:
            register_generated_file_from_tool_file(
                db.session,
                tool_file,
                owner_user_id=user_id,
                source_kind="ppt_artifact",
                commit=True,
            )
        except Exception:
            db.session.rollback()
            logger.exception(
                "Generated asset indexing failed without affecting PPTX artifact: tool_file_id=%s",
                tool_file.id,
            )
        download_url = sign_tool_file(str(tool_file.id), ".pptx", for_external=True)
        separator = "&" if "?" in download_url else "?"
        download_url = f"{download_url}{separator}as_attachment=true"

        return {
            "file_id": str(tool_file.id),
            "filename": tool_file.name,
            "size": tool_file.size,
            "mime_type": PPTX_MIME_TYPE,
            "download_url": download_url,
        }, 201
