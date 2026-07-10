import logging
from datetime import datetime
from typing import Any

from flask import request
from pydantic import BaseModel, Field, field_validator
from sqlalchemy.orm import sessionmaker
from werkzeug.exceptions import BadRequest, InternalServerError, NotFound

from controllers.common.controller_schemas import WorkflowRunPayload
from controllers.common.fields import SimpleResultResponse
from controllers.common.schema import query_params_from_model, register_response_schema_models, register_schema_model
from controllers.console.app.error import (
    CompletionRequestError,
    ProviderModelCurrentlyNotSupportError,
    ProviderNotInitializeError,
    ProviderQuotaExceededError,
)
from controllers.console.explore.error import NotWorkflowAppError
from controllers.console.explore.wraps import InstalledAppResource
from controllers.web.error import InvokeRateLimitError as InvokeRateLimitHttpError
from core.app.apps.base_app_queue_manager import AppQueueManager
from core.app.entities.app_invoke_entities import InvokeFrom
from core.errors.error import (
    ModelCurrentlyNotSupportError,
    ProviderTokenNotInitError,
    QuotaExceededError,
)
from extensions.ext_redis import redis_client
from extensions.ext_database import db
from fields.base import ResponseModel
from graphon.graph_engine.manager import GraphEngineManager
from graphon.model_runtime.errors.invoke import InvokeError
from libs import helper
from libs.helper import uuid_value
from libs.login import current_account_with_tenant
from models.model import App, AppMode, InstalledApp
from services.app_generate_service import AppGenerateService
from services.errors.llm import InvokeRateLimitError
from services.workflow_run_history_service import WorkflowRunHistoryService

from .. import console_ns

logger = logging.getLogger(__name__)

class WorkflowRunHistoryQuery(BaseModel):
    last_id: str | None = Field(default=None, description="Last workflow run ID from the previous page")
    limit: int = Field(default=20, ge=1, le=100, description="Number of runs per page")

    @field_validator("last_id")
    @classmethod
    def _validate_last_id(cls, value: str | None) -> str | None:
        return uuid_value(value) if value else None


class WorkflowRunHistoryItemResponse(ResponseModel):
    id: str
    status: str
    request: str
    created_at: int
    finished_at: int | None = None
    elapsed_time: float
    duration: str | None = None
    aspect_ratio: str | None = None
    resolution: str | None = None
    error: str | None = None
    video_url: str | None = None
    character_image_url: str | None = None
    scene_image_url: str | None = None

    @field_validator("created_at", "finished_at", mode="before")
    @classmethod
    def _normalize_timestamp(cls, value: datetime | int | None) -> int | None:
        return helper.to_timestamp(value)


class WorkflowRunHistoryDetailResponse(WorkflowRunHistoryItemResponse):
    inputs: dict[str, Any]
    outputs: dict[str, Any]
    result: str
    script: str
    storyboard: str
    title: str | None = None
    intent: str | None = None


class WorkflowRunHistoryPaginationResponse(ResponseModel):
    limit: int
    has_more: bool
    last_id: str | None = None
    data: list[WorkflowRunHistoryItemResponse]


register_schema_model(console_ns, WorkflowRunPayload)
register_schema_model(console_ns, WorkflowRunHistoryQuery)
register_response_schema_models(
    console_ns,
    SimpleResultResponse,
    WorkflowRunHistoryItemResponse,
    WorkflowRunHistoryDetailResponse,
    WorkflowRunHistoryPaginationResponse,
)


def _ensure_workflow_app(installed_app: InstalledApp) -> App:
    """Return the installed workflow app without allowing other app modes into history APIs."""
    app_model = installed_app.app
    if not app_model or AppMode.value_of(app_model.mode) != AppMode.WORKFLOW:
        raise NotWorkflowAppError()
    return app_model


@console_ns.route("/installed-apps/<uuid:installed_app_id>/workflow-runs")
class InstalledAppWorkflowRunHistoryApi(InstalledAppResource):
    @console_ns.doc(params=query_params_from_model(WorkflowRunHistoryQuery))
    @console_ns.response(
        200,
        "Workflow run history retrieved successfully",
        console_ns.models[WorkflowRunHistoryPaginationResponse.__name__],
    )
    def get(self, installed_app: InstalledApp):
        """List only the current account's installed-app workflow runs."""
        current_user, _ = current_account_with_tenant()
        app_model = _ensure_workflow_app(installed_app)
        query = WorkflowRunHistoryQuery.model_validate(request.args.to_dict(flat=True))

        with sessionmaker(db.engine, expire_on_commit=False).begin() as session:
            try:
                page = WorkflowRunHistoryService.get_page(
                    session=session,
                    tenant_id=app_model.tenant_id,
                    app_id=app_model.id,
                    account_id=current_user.id,
                    last_id=query.last_id,
                    limit=query.limit,
                )
            except ValueError as error:
                raise BadRequest(str(error)) from error

        return WorkflowRunHistoryPaginationResponse.model_validate(
            {
                "limit": query.limit,
                "has_more": page.has_more,
                "last_id": page.last_id,
                "data": page.data,
            }
        ).model_dump(mode="json")


@console_ns.route("/installed-apps/<uuid:installed_app_id>/workflow-runs/<uuid:run_id>")
class InstalledAppWorkflowRunHistoryDetailApi(InstalledAppResource):
    @console_ns.response(
        200,
        "Workflow run history detail retrieved successfully",
        console_ns.models[WorkflowRunHistoryDetailResponse.__name__],
    )
    def get(self, installed_app: InstalledApp, run_id: str):
        """Read one current-account run; out-of-scope IDs are indistinguishable from missing IDs."""
        current_user, _ = current_account_with_tenant()
        app_model = _ensure_workflow_app(installed_app)

        with sessionmaker(db.engine, expire_on_commit=False).begin() as session:
            detail = WorkflowRunHistoryService.get_detail(
                session=session,
                tenant_id=app_model.tenant_id,
                app_id=app_model.id,
                account_id=current_user.id,
                run_id=str(run_id),
            )
        if detail is None:
            raise NotFound("Workflow run not found")
        return WorkflowRunHistoryDetailResponse.model_validate(detail).model_dump(mode="json")


@console_ns.route("/installed-apps/<uuid:installed_app_id>/workflows/run")
class InstalledAppWorkflowRunApi(InstalledAppResource):
    @console_ns.expect(console_ns.models[WorkflowRunPayload.__name__])
    def post(self, installed_app: InstalledApp):
        """
        Run workflow
        """
        current_user, _ = current_account_with_tenant()
        app_model = installed_app.app
        if not app_model:
            raise NotWorkflowAppError()
        app_mode = AppMode.value_of(app_model.mode)
        if app_mode != AppMode.WORKFLOW:
            raise NotWorkflowAppError()

        payload = WorkflowRunPayload.model_validate(console_ns.payload or {})
        args = payload.model_dump(exclude_none=True)
        try:
            response = AppGenerateService.generate(
                app_model=app_model, user=current_user, args=args, invoke_from=InvokeFrom.EXPLORE, streaming=True
            )

            return helper.compact_generate_response(response)
        except ProviderTokenNotInitError as ex:
            raise ProviderNotInitializeError(ex.description)
        except QuotaExceededError:
            raise ProviderQuotaExceededError()
        except ModelCurrentlyNotSupportError:
            raise ProviderModelCurrentlyNotSupportError()
        except InvokeError as e:
            raise CompletionRequestError(e.description)
        except InvokeRateLimitError as ex:
            raise InvokeRateLimitHttpError(ex.description)
        except ValueError as e:
            raise e
        except Exception:
            logger.exception("internal server error.")
            raise InternalServerError()


@console_ns.route("/installed-apps/<uuid:installed_app_id>/workflows/tasks/<string:task_id>/stop")
class InstalledAppWorkflowTaskStopApi(InstalledAppResource):
    @console_ns.response(200, "Success", console_ns.models[SimpleResultResponse.__name__])
    def post(self, installed_app: InstalledApp, task_id: str):
        """
        Stop workflow task
        """
        app_model = installed_app.app
        if not app_model:
            raise NotWorkflowAppError()
        app_mode = AppMode.value_of(app_model.mode)
        if app_mode != AppMode.WORKFLOW:
            raise NotWorkflowAppError()

        # Stop using both mechanisms for backward compatibility
        # Legacy stop flag mechanism (without user check)
        AppQueueManager.set_stop_flag_no_user_check(task_id)

        # New graph engine command channel mechanism
        GraphEngineManager(redis_client).send_stop_command(task_id)

        return {"result": "success"}
