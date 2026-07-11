"""Console APIs for tenant-scoped generated content assets.

Owners and admins may request the whole tenant library; other members are always
restricted to their own Account ID. Knowledge-base permissions do not participate in
this authorization boundary.
"""

from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import quote
from uuid import UUID

from flask import Response, request
from flask_restx import Resource
from pydantic import BaseModel, Field, field_validator
from werkzeug.exceptions import NotFound

from controllers.common.fields import SimpleResultResponse
from controllers.common.schema import query_params_from_model, register_response_schema_models, register_schema_models
from controllers.console import console_ns
from controllers.console.datasets.error import InvalidActionError
from controllers.console.wraps import account_initialization_required, setup_required
from extensions.ext_database import db
from fields.base import ResponseModel
from libs.helper import dump_response, uuid_value
from libs.login import current_account_with_tenant, login_required
from services.generated_file_service import (
    backfill_generated_files_for_user,
    build_generated_file_download_url,
    convert_generated_file_to_pdf,
    get_generated_file_for_user,
    list_generated_files,
    serialize_generated_asset,
    soft_delete_generated_file,
)


class GeneratedFileListQuery(BaseModel):
    page: int = Field(default=1, ge=1)
    limit: int = Field(default=50, ge=1, le=100)
    keyword: str | None = None
    file_type: str | None = None
    source_app_id: str | None = None
    source_app_ids: str | None = None
    owner_user_ids: str | None = None
    source_kind: str | None = None
    storage_type: str | None = None
    created_after: datetime | None = None
    created_before: datetime | None = None
    include_all: bool = True
    sort: str = "-created_at"

    @field_validator("source_app_id", "source_app_ids")
    @classmethod
    def validate_app_filter(cls, value: str | None) -> str | None:
        if not value:
            return None
        values = []
        for item in value.split(","):
            item = item.strip()
            if item == "unknown":
                values.append(item)
            elif item:
                values.append(uuid_value(item))
        return ",".join(values) or None

    @field_validator("owner_user_ids")
    @classmethod
    def validate_owner_filter(cls, value: str | None) -> str | None:
        if not value:
            return None
        values = [uuid_value(item.strip()) for item in value.split(",") if item.strip()]
        return ",".join(values) or None

    @field_validator("created_after", "created_before", mode="before")
    @classmethod
    def normalize_timestamp(cls, value: Any) -> Any:
        if isinstance(value, str) and value.strip().isdigit():
            return datetime.fromtimestamp(int(value), tz=UTC).replace(tzinfo=None)
        if isinstance(value, int | float):
            return datetime.fromtimestamp(value, tz=UTC).replace(tzinfo=None)
        if isinstance(value, datetime) and value.tzinfo:
            return value.astimezone(UTC).replace(tzinfo=None)
        return value


class GeneratedAssetFacetItem(ResponseModel):
    id: str
    name: str
    count: int


class GeneratedAssetFacets(ResponseModel):
    accounts: list[GeneratedAssetFacetItem]
    apps: list[GeneratedAssetFacetItem]
    file_types: list[GeneratedAssetFacetItem]
    source_kinds: list[GeneratedAssetFacetItem]
    storage_types: list[GeneratedAssetFacetItem]


class GeneratedAssetStats(ResponseModel):
    total: int
    total_size: int
    by_type: dict[str, int]


class GeneratedAssetItem(ResponseModel):
    id: str
    name: str
    mime_type: str
    file_type: str
    extension: str
    size: int
    created_at: int | None
    source_app_id: str | None
    source_app_name: str | None
    source_conversation_id: str | None
    source_message_id: str | None
    source_workflow_run_id: str | None
    owner_user_id: str
    owner_name: str | None
    storage_type: str
    source_kind: str
    source_url: str | None
    thumbnail_url: str | None
    asset_metadata: dict[str, Any]
    preview_kind: str
    preview_url: str
    download_url: str


class GeneratedAssetListResponse(ResponseModel):
    data: list[GeneratedAssetItem]
    page: int
    limit: int
    total: int
    has_more: bool
    facets: GeneratedAssetFacets
    stats: GeneratedAssetStats


class GeneratedAssetPreviewResponse(GeneratedAssetItem):
    mode: str
    original_file_type: str


class GeneratedAssetDownloadResponse(ResponseModel):
    url: str


register_schema_models(console_ns, GeneratedFileListQuery)
register_response_schema_models(
    console_ns,
    GeneratedAssetListResponse,
    GeneratedAssetPreviewResponse,
    GeneratedAssetDownloadResponse,
    SimpleResultResponse,
)


@console_ns.route("/generated-files", "/generated-assets")
class GeneratedFileListApi(Resource):
    @console_ns.doc(params=query_params_from_model(GeneratedFileListQuery))
    @console_ns.response(200, "Generated assets retrieved", console_ns.models[GeneratedAssetListResponse.__name__])
    @setup_required
    @login_required
    @account_initialization_required
    def get(self):
        current_user, tenant_id = current_account_with_tenant()
        query = GeneratedFileListQuery.model_validate(request.args.to_dict())
        backfill_generated_files_for_user(db.session, tenant_id=tenant_id, user_id=current_user.id)
        result = list_generated_files(
            db.session,
            tenant_id=tenant_id,
            current_user=current_user,
            page=query.page,
            limit=query.limit,
            keyword=query.keyword,
            file_type=query.file_type,
            source_app_id=query.source_app_id,
            source_app_ids=query.source_app_ids,
            owner_user_ids=query.owner_user_ids,
            source_kind=query.source_kind,
            storage_type=query.storage_type,
            created_after=query.created_after,
            created_before=query.created_before,
            include_all=query.include_all,
            sort=query.sort,
        )
        return dump_response(GeneratedAssetListResponse, result)


@console_ns.route("/generated-files/<uuid:file_id>", "/generated-assets/<uuid:file_id>")
class GeneratedFileApi(Resource):
    @console_ns.response(200, "Generated asset preview", console_ns.models[GeneratedAssetPreviewResponse.__name__])
    @setup_required
    @login_required
    @account_initialization_required
    def get(self, file_id: UUID):
        generated_file = _get_console_asset(file_id)
        result = serialize_generated_asset(
            generated_file,
            source_app_name=None,
            owner_name=None,
        )
        return dump_response(GeneratedAssetPreviewResponse, result)

    @setup_required
    @login_required
    @account_initialization_required
    def delete(self, file_id: UUID):
        generated_file = _get_console_asset(file_id)
        soft_delete_generated_file(db.session, generated_file)
        return {"result": "success"}


@console_ns.route(
    "/generated-files/<uuid:file_id>/download-url",
    "/generated-assets/<uuid:file_id>/download-url",
)
class GeneratedFileDownloadApi(Resource):
    @console_ns.response(
        200, "Generated asset download URL", console_ns.models[GeneratedAssetDownloadResponse.__name__]
    )
    @setup_required
    @login_required
    @account_initialization_required
    def get(self, file_id: UUID):
        generated_file = _get_console_asset(file_id)
        try:
            url = build_generated_file_download_url(generated_file)
        except FileNotFoundError as exc:
            raise NotFound(str(exc)) from exc
        return dump_response(GeneratedAssetDownloadResponse, {"url": url})


@console_ns.route(
    "/generated-files/<uuid:file_id>/converted-preview",
    "/generated-assets/<uuid:file_id>/converted-preview",
)
class GeneratedFileConvertedPreviewApi(Resource):
    @setup_required
    @login_required
    @account_initialization_required
    def get(self, file_id: UUID):
        generated_file = _get_console_asset(file_id)
        try:
            pdf_path = convert_generated_file_to_pdf(db.session, generated_file)
        except (FileNotFoundError, RuntimeError, ValueError) as exc:
            raise InvalidActionError(str(exc)) from exc

        pdf_bytes = pdf_path.read_bytes()
        response = Response(pdf_bytes, mimetype="application/pdf", direct_passthrough=False)
        response.headers["Accept-Ranges"] = "bytes"
        response.headers["Content-Length"] = str(len(pdf_bytes))
        preview_name = f"{Path(generated_file.name).stem or 'generated-file'}.pdf"
        response.headers["Content-Disposition"] = f"inline; filename*=UTF-8''{quote(preview_name)}"
        return response


def _get_console_asset(file_id: UUID):
    current_user, tenant_id = current_account_with_tenant()
    generated_file = get_generated_file_for_user(
        db.session,
        generated_file_id=str(file_id),
        tenant_id=tenant_id,
        current_user=current_user,
    )
    if not generated_file:
        raise NotFound("Generated asset not found.")
    return generated_file
