from datetime import datetime
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from flask import Flask
from werkzeug.exceptions import BadRequest, InternalServerError, NotFound

import controllers.console.explore.workflow as workflow_module
from controllers.console.explore.error import NotWorkflowAppError
from controllers.console.explore.workflow import (
    InstalledAppWorkflowRunApi,
    InstalledAppWorkflowRunHistoryApi,
    InstalledAppWorkflowRunHistoryDetailApi,
    InstalledAppWorkflowTaskStopApi,
)
from controllers.web.error import InvokeRateLimitError as InvokeRateLimitHttpError
from models.model import AppMode
from services.errors.llm import InvokeRateLimitError
from services.workflow_run_history_service import WorkflowRunHistoryPage


def unwrap(func):
    while hasattr(func, "__wrapped__"):
        func = func.__wrapped__
    return func


@pytest.fixture
def app():
    app = Flask(__name__)
    app.config["TESTING"] = True
    return app


@pytest.fixture
def user():
    return MagicMock()


@pytest.fixture
def workflow_app():
    app = MagicMock()
    app.mode = AppMode.WORKFLOW
    return app


@pytest.fixture
def installed_workflow_app(workflow_app):
    return MagicMock(app=workflow_app)


@pytest.fixture
def non_workflow_installed_app():
    app = MagicMock()
    app.mode = AppMode.CHAT
    return MagicMock(app=app)


@pytest.fixture
def payload():
    return {"inputs": {"a": 1}}


class TestInstalledAppWorkflowRunApi:
    def test_not_workflow_app(self, app: Flask, non_workflow_installed_app):
        api = InstalledAppWorkflowRunApi()
        method = unwrap(api.post)

        with (
            app.test_request_context("/"),
            patch(
                "controllers.console.explore.workflow.current_account_with_tenant",
                return_value=(MagicMock(), None),
            ),
        ):
            with pytest.raises(NotWorkflowAppError):
                method(non_workflow_installed_app)

    def test_success(self, app: Flask, installed_workflow_app, user, payload):
        api = InstalledAppWorkflowRunApi()
        method = unwrap(api.post)

        with (
            app.test_request_context("/", json=payload),
            patch(
                "controllers.console.explore.workflow.current_account_with_tenant",
                return_value=(user, None),
            ),
            patch(
                "controllers.console.explore.workflow.AppGenerateService.generate",
                return_value=MagicMock(),
            ) as generate_mock,
        ):
            result = method(installed_workflow_app)

            generate_mock.assert_called_once()
            assert result is not None

    def test_rate_limit_error(self, app: Flask, installed_workflow_app, user, payload):
        api = InstalledAppWorkflowRunApi()
        method = unwrap(api.post)

        with (
            app.test_request_context("/", json=payload),
            patch(
                "controllers.console.explore.workflow.current_account_with_tenant",
                return_value=(user, None),
            ),
            patch(
                "controllers.console.explore.workflow.AppGenerateService.generate",
                side_effect=InvokeRateLimitError("rate limit"),
            ),
        ):
            with pytest.raises(InvokeRateLimitHttpError):
                method(installed_workflow_app)

    def test_unexpected_exception(self, app: Flask, installed_workflow_app, user, payload):
        api = InstalledAppWorkflowRunApi()
        method = unwrap(api.post)

        with (
            app.test_request_context("/", json=payload),
            patch(
                "controllers.console.explore.workflow.current_account_with_tenant",
                return_value=(user, None),
            ),
            patch(
                "controllers.console.explore.workflow.AppGenerateService.generate",
                side_effect=Exception("boom"),
            ),
        ):
            with pytest.raises(InternalServerError):
                method(installed_workflow_app)


class TestInstalledAppWorkflowTaskStopApi:
    def test_not_workflow_app(self, non_workflow_installed_app):
        api = InstalledAppWorkflowTaskStopApi()
        method = unwrap(api.post)

        with pytest.raises(NotWorkflowAppError):
            method(non_workflow_installed_app, "task-1")

    def test_success(self, installed_workflow_app):
        api = InstalledAppWorkflowTaskStopApi()
        method = unwrap(api.post)

        with (
            patch("controllers.console.explore.workflow.AppQueueManager.set_stop_flag_no_user_check") as stop_flag,
            patch("controllers.console.explore.workflow.GraphEngineManager.send_stop_command") as send_stop,
        ):
            result = method(installed_workflow_app, "task-1")

            stop_flag.assert_called_once_with("task-1")
            send_stop.assert_called_once_with("task-1")
            assert result == {"result": "success"}


def _history_item():
    return {
        "id": "run-1",
        "status": "succeeded",
        "request": "Create an MMB bear video",
        "created_at": datetime(2026, 7, 10, 12, 0, 0),
        "finished_at": datetime(2026, 7, 10, 12, 0, 5),
        "elapsed_time": 5.0,
        "duration": "5",
        "aspect_ratio": "16:9",
        "resolution": "480p",
        "error": None,
        "video_url": "https://example.com/video.mp4",
        "character_image_url": None,
        "scene_image_url": None,
    }


def _sessionmaker_mock():
    session = MagicMock()
    maker = MagicMock()
    maker.return_value.begin.return_value.__enter__.return_value = session
    return maker, session


class TestInstalledAppWorkflowRunHistoryApi:
    def test_should_list_only_with_current_account_scope(self, app: Flask, installed_workflow_app, user):
        api = InstalledAppWorkflowRunHistoryApi()
        method = unwrap(api.get)
        user.id = "account-1"
        installed_workflow_app.app.id = "app-1"
        installed_workflow_app.app.tenant_id = "tenant-1"
        maker, session = _sessionmaker_mock()
        page = WorkflowRunHistoryPage(data=[_history_item()], has_more=False, last_id=None)

        with (
            app.test_request_context("/", query_string={"limit": 20}),
            patch.object(workflow_module, "current_account_with_tenant", return_value=(user, "consumer-tenant")),
            patch.object(workflow_module, "db", SimpleNamespace(engine=MagicMock())),
            patch.object(workflow_module, "sessionmaker", maker),
            patch.object(workflow_module.WorkflowRunHistoryService, "get_page", return_value=page) as get_page,
        ):
            result = method(installed_workflow_app)

        get_page.assert_called_once_with(
            session=session,
            tenant_id="tenant-1",
            app_id="app-1",
            account_id="account-1",
            last_id=None,
            limit=20,
        )
        assert result["data"][0]["id"] == "run-1"

    def test_should_reject_cursor_outside_account_scope(self, app: Flask, installed_workflow_app, user):
        api = InstalledAppWorkflowRunHistoryApi()
        method = unwrap(api.get)
        maker, _ = _sessionmaker_mock()

        with (
            app.test_request_context("/", query_string={"last_id": "2a68ef69-f589-478f-90d7-cea9f5d958e8"}),
            patch.object(workflow_module, "current_account_with_tenant", return_value=(user, "tenant-1")),
            patch.object(workflow_module, "db", SimpleNamespace(engine=MagicMock())),
            patch.object(workflow_module, "sessionmaker", maker),
            patch.object(
                workflow_module.WorkflowRunHistoryService,
                "get_page",
                side_effect=ValueError("Invalid workflow run cursor"),
            ),
        ):
            with pytest.raises(BadRequest):
                method(installed_workflow_app)

    def test_should_reject_non_workflow_app(self, non_workflow_installed_app):
        api = InstalledAppWorkflowRunHistoryApi()
        method = unwrap(api.get)

        with patch.object(workflow_module, "current_account_with_tenant", return_value=(MagicMock(), "tenant-1")):
            with pytest.raises(NotWorkflowAppError):
                method(non_workflow_installed_app)


class TestInstalledAppWorkflowRunHistoryDetailApi:
    def test_should_return_account_owned_detail(self, installed_workflow_app, user):
        api = InstalledAppWorkflowRunHistoryDetailApi()
        method = unwrap(api.get)
        user.id = "account-1"
        installed_workflow_app.app.id = "app-1"
        installed_workflow_app.app.tenant_id = "tenant-1"
        maker, session = _sessionmaker_mock()
        detail = {
            **_history_item(),
            "inputs": {"video_request": "Create an MMB bear video"},
            "outputs": {"video_url": "https://example.com/video.mp4"},
            "result": "# Result",
            "script": "Script",
            "storyboard": "Storyboard",
        }

        with (
            patch.object(workflow_module, "current_account_with_tenant", return_value=(user, "consumer-tenant")),
            patch.object(workflow_module, "db", SimpleNamespace(engine=MagicMock())),
            patch.object(workflow_module, "sessionmaker", maker),
            patch.object(workflow_module.WorkflowRunHistoryService, "get_detail", return_value=detail) as get_detail,
        ):
            result = method(installed_workflow_app, "run-1")

        get_detail.assert_called_once_with(
            session=session,
            tenant_id="tenant-1",
            app_id="app-1",
            account_id="account-1",
            run_id="run-1",
        )
        assert result["video_url"] == "https://example.com/video.mp4"

    def test_should_hide_out_of_scope_run_as_not_found(self, installed_workflow_app, user):
        api = InstalledAppWorkflowRunHistoryDetailApi()
        method = unwrap(api.get)
        maker, _ = _sessionmaker_mock()

        with (
            patch.object(workflow_module, "current_account_with_tenant", return_value=(user, "tenant-1")),
            patch.object(workflow_module, "db", SimpleNamespace(engine=MagicMock())),
            patch.object(workflow_module, "sessionmaker", maker),
            patch.object(workflow_module.WorkflowRunHistoryService, "get_detail", return_value=None),
        ):
            with pytest.raises(NotFound):
                method(installed_workflow_app, "other-account-run")
