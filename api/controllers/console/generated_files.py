from uuid import UUID

from flask import request
from flask_restx import Resource
from pydantic import BaseModel, Field, field_validator
from werkzeug.exceptions import NotFound

from controllers.common.fields import SimpleResultResponse
from controllers.common.schema import register_response_schema_models, register_schema_models
from controllers.console import console_ns
from controllers.console.wraps import account_initialization_required, setup_required
from extensions.ext_database import db
from libs.helper import uuid_value
from libs.login import current_account_with_tenant, login_required
from services.generated_file_service import (
    backfill_generated_files_for_user,
    build_generated_file_download_url,
    build_generated_file_preview_config,
    get_generated_file_for_user,
    list_generated_files,
    soft_delete_generated_file,
)


class GeneratedFileListQuery(BaseModel):
    page: int = Field(default=1, ge=1)
    limit: int = Field(default=50, ge=1, le=100)
    keyword: str | None = None
    file_type: str | None = None
    source_app_id: str | None = None
    include_all: bool = False
    sort: str = "-created_at"

    @field_validator("source_app_id")
    @classmethod
    def validate_uuid(cls, value: str | None) -> str | None:
        if not value:
            return None
        return uuid_value(value)


register_schema_models(console_ns, GeneratedFileListQuery)
register_response_schema_models(console_ns, SimpleResultResponse)


@console_ns.route("/generated-files")
class GeneratedFileListApi(Resource):
    @setup_required
    @login_required
    @account_initialization_required
    def get(self):
        current_user, tenant_id = current_account_with_tenant()
        query = GeneratedFileListQuery.model_validate(request.args.to_dict())
        backfill_generated_files_for_user(db.session, tenant_id=tenant_id, user_id=current_user.id)
        return list_generated_files(
            db.session,
            tenant_id=tenant_id,
            current_user=current_user,
            page=query.page,
            limit=query.limit,
            keyword=query.keyword,
            file_type=query.file_type,
            source_app_id=query.source_app_id,
            include_all=query.include_all,
            sort=query.sort,
        )


@console_ns.route("/generated-files/<uuid:file_id>")
class GeneratedFileApi(Resource):
    @setup_required
    @login_required
    @account_initialization_required
    def get(self, file_id: UUID):
        current_user, tenant_id = current_account_with_tenant()
        generated_file = get_generated_file_for_user(
            db.session,
            generated_file_id=str(file_id),
            tenant_id=tenant_id,
            current_user=current_user,
        )
        if not generated_file:
            raise NotFound("Generated file not found.")
        return build_generated_file_preview_config(generated_file)

    @setup_required
    @login_required
    @account_initialization_required
    def delete(self, file_id: UUID):
        current_user, tenant_id = current_account_with_tenant()
        generated_file = get_generated_file_for_user(
            db.session,
            generated_file_id=str(file_id),
            tenant_id=tenant_id,
            current_user=current_user,
        )
        if not generated_file:
            raise NotFound("Generated file not found.")
        soft_delete_generated_file(db.session, generated_file)
        return {"result": "success"}


@console_ns.route("/generated-files/<uuid:file_id>/download-url")
class GeneratedFileDownloadApi(Resource):
    @setup_required
    @login_required
    @account_initialization_required
    def get(self, file_id: UUID):
        current_user, tenant_id = current_account_with_tenant()
        generated_file = get_generated_file_for_user(
            db.session,
            generated_file_id=str(file_id),
            tenant_id=tenant_id,
            current_user=current_user,
        )
        if not generated_file:
            raise NotFound("Generated file not found.")
        return {"url": build_generated_file_download_url(generated_file)}
