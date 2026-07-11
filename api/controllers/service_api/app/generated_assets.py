"""Service API endpoints for one app-scoped EndUser's generated assets.

Every operation requires the app API key and the stable ``user`` query argument.
Asset lookup predicates include tenant, app, and EndUser IDs so an otherwise valid
asset UUID cannot be used across applications or external users.
"""

from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import quote, urlencode
from uuid import UUID

from flask import Response, redirect, request
from flask_restx import Resource
from pydantic import BaseModel, Field, field_validator
from werkzeug.exceptions import BadRequest, NotFound

from controllers.common.schema import query_params_from_model, register_response_schema_models, register_schema_models
from controllers.service_api import service_api_ns
from controllers.service_api.wraps import FetchUserArg, WhereisUserArg, validate_app_token
from extensions.ext_database import db
from fields.base import ResponseModel
from libs.helper import dump_response
from models.model import App, EndUser
from services.generated_file_service import (
    backfill_generated_files_for_user,
    build_generated_file_download_url,
    convert_generated_file_to_pdf,
    get_generated_file_for_end_user,
    list_generated_files_for_end_user,
    serialize_generated_asset,
)


class GeneratedAssetServiceListQuery(BaseModel):
    user: str = Field(min_length=1, max_length=255)
    page: int = Field(default=1, ge=1)
    limit: int = Field(default=50, ge=1, le=100)
    keyword: str | None = None
    file_type: str | None = None
    source_kind: str | None = None
    created_after: datetime | None = None
    created_before: datetime | None = None
    sort: str = "-created_at"

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


class GeneratedAssetServiceItem(ResponseModel):
    id: str
    name: str
    mime_type: str
    file_type: str
    extension: str
    original_file_type: str
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


class GeneratedAssetServiceListResponse(ResponseModel):
    data: list[GeneratedAssetServiceItem]
    page: int
    limit: int
    total: int
    has_more: bool
    facets: dict[str, list[dict[str, Any]]]
    stats: dict[str, Any]


register_schema_models(service_api_ns, GeneratedAssetServiceListQuery)
register_response_schema_models(
    service_api_ns,
    GeneratedAssetServiceItem,
    GeneratedAssetServiceListResponse,
)


@service_api_ns.route("/generated-assets")
class GeneratedAssetServiceListApi(Resource):
    @service_api_ns.doc(params=query_params_from_model(GeneratedAssetServiceListQuery))
    @service_api_ns.response(
        200,
        "Generated assets retrieved",
        service_api_ns.models[GeneratedAssetServiceListResponse.__name__],
    )
    @validate_app_token(fetch_user_arg=FetchUserArg(fetch_from=WhereisUserArg.QUERY, required=True))
    def get(self, app_model: App, end_user: EndUser):
        query = GeneratedAssetServiceListQuery.model_validate(request.args.to_dict())
        backfill_generated_files_for_user(db.session, tenant_id=app_model.tenant_id, user_id=end_user.id)
        result = list_generated_files_for_end_user(
            db.session,
            tenant_id=app_model.tenant_id,
            app_id=app_model.id,
            end_user_id=end_user.id,
            page=query.page,
            limit=query.limit,
            keyword=query.keyword,
            file_type=query.file_type,
            source_kind=query.source_kind,
            created_after=query.created_after,
            created_before=query.created_before,
            sort=query.sort,
        )
        for item in result["data"]:
            _set_service_urls(item, user=query.user)
        return dump_response(GeneratedAssetServiceListResponse, result)


@service_api_ns.route("/generated-assets/<uuid:file_id>")
class GeneratedAssetServiceApi(Resource):
    @service_api_ns.response(
        200,
        "Generated asset retrieved",
        service_api_ns.models[GeneratedAssetServiceItem.__name__],
    )
    @validate_app_token(fetch_user_arg=FetchUserArg(fetch_from=WhereisUserArg.QUERY, required=True))
    def get(self, app_model: App, end_user: EndUser, file_id: UUID):
        generated_file = _get_service_asset(app_model, end_user, file_id)
        item = serialize_generated_asset(
            generated_file,
            source_app_name=app_model.name,
            owner_name=end_user.name or end_user.session_id,
        )
        _set_service_urls(item, user=request.args["user"])
        return dump_response(GeneratedAssetServiceItem, item)


@service_api_ns.route("/generated-assets/<uuid:file_id>/download")
class GeneratedAssetServiceDownloadApi(Resource):
    @validate_app_token(fetch_user_arg=FetchUserArg(fetch_from=WhereisUserArg.QUERY, required=True))
    def get(self, app_model: App, end_user: EndUser, file_id: UUID):
        generated_file = _get_service_asset(app_model, end_user, file_id)
        try:
            url = build_generated_file_download_url(generated_file)
        except FileNotFoundError as exc:
            raise NotFound(str(exc)) from exc
        return redirect(url, code=302)


@service_api_ns.route("/generated-assets/<uuid:file_id>/converted-preview")
class GeneratedAssetServiceConvertedPreviewApi(Resource):
    @validate_app_token(fetch_user_arg=FetchUserArg(fetch_from=WhereisUserArg.QUERY, required=True))
    def get(self, app_model: App, end_user: EndUser, file_id: UUID):
        generated_file = _get_service_asset(app_model, end_user, file_id)
        try:
            pdf_path = convert_generated_file_to_pdf(db.session, generated_file)
        except (FileNotFoundError, RuntimeError, ValueError) as exc:
            raise BadRequest(str(exc)) from exc
        pdf_bytes = pdf_path.read_bytes()
        response = Response(pdf_bytes, mimetype="application/pdf", direct_passthrough=False)
        response.headers["Content-Length"] = str(len(pdf_bytes))
        preview_name = f"{Path(generated_file.name).stem or 'generated-file'}.pdf"
        response.headers["Content-Disposition"] = f"inline; filename*=UTF-8''{quote(preview_name)}"
        return response


def _get_service_asset(app_model: App, end_user: EndUser, file_id: UUID):
    generated_file = get_generated_file_for_end_user(
        db.session,
        generated_file_id=str(file_id),
        tenant_id=app_model.tenant_id,
        app_id=app_model.id,
        end_user_id=end_user.id,
    )
    if not generated_file:
        raise NotFound("Generated asset not found.")
    return generated_file


def _set_service_urls(item: dict[str, Any], *, user: str) -> None:
    query = urlencode({"user": user})
    base_path = f"/v1/generated-assets/{item['id']}"
    item["download_url"] = f"{base_path}/download?{query}"
    if item["preview_kind"] == "converted_pdf":
        item["preview_url"] = f"{base_path}/converted-preview?{query}"
