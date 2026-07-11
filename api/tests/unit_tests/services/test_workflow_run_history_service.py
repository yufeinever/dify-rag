from datetime import datetime
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from graphon.enums import WorkflowExecutionStatus
from services.workflow_run_history_service import WorkflowRunHistoryService


def _run(**overrides):
    values = {
        "id": "run-1",
        "status": WorkflowExecutionStatus.SUCCEEDED,
        "error": None,
        "created_at": datetime(2026, 7, 10, 12, 0, 0),
        "finished_at": datetime(2026, 7, 10, 12, 0, 5),
        "elapsed_time": 5.0,
        "inputs_dict": {
            "video_request": "MMB bear flies through clouds",
            "duration": 5,
            "aspect_ratio": "16:9",
            "resolution": "480p",
        },
        "outputs_dict": {
            "result": "# Story",
            "script": "A short script",
            "storyboard": "1. Wide shot",
            "video_url": "https://example.com/video.mp4",
            "character_image_url": "data:image/png;base64,large",
            "scene_image_url": "/files/scene.jpg",
        },
    }
    values.update(overrides)
    return SimpleNamespace(**values)


class TestWorkflowRunHistorySerialization:
    def test_should_omit_data_uri_from_list_preview(self) -> None:
        item = WorkflowRunHistoryService.to_list_item(_run())

        assert item["video_url"] == "https://example.com/video.mp4"
        assert item["character_image_url"] is None
        assert item["scene_image_url"] == "/files/scene.jpg"
        assert item["duration"] == "5"

    def test_should_mark_succeeded_run_without_video_as_failed(self) -> None:
        run = _run(outputs_dict={"result": "legacy markdown"})

        detail = WorkflowRunHistoryService.to_detail(run)

        assert detail["status"] == WorkflowExecutionStatus.FAILED.value
        assert detail["error"] == "The workflow succeeded but did not return a playable video URL."
        assert detail["result"] == "legacy markdown"

    def test_should_serialize_legacy_run_with_missing_fields(self) -> None:
        run = _run(status=WorkflowExecutionStatus.FAILED, inputs_dict={}, outputs_dict={}, error="boom")

        detail = WorkflowRunHistoryService.to_detail(run)

        assert detail["request"] == ""
        assert detail["script"] == ""
        assert detail["storyboard"] == ""
        assert detail["video_url"] is None
        assert detail["error"] == "boom"

    def test_should_restore_title_and_intent_from_legacy_markdown(self) -> None:
        run = _run(
            outputs_dict={
                "result": "# Cloud House\n\n**创作意图**：A warm fantasy short video.\n\n## 脚本\n...",
                "video_url": "https://example.com/video.mp4",
            }
        )

        detail = WorkflowRunHistoryService.to_detail(run)

        assert detail["title"] == "Cloud House"
        assert detail["intent"] == "A warm fantasy short video."

    def test_should_prefer_local_video_and_hide_confirmed_expired_source(self) -> None:
        run = _run()

        local = WorkflowRunHistoryService.to_detail(run, "/files/tools/local.mp4?signed=1")
        expired = WorkflowRunHistoryService.to_detail(run, video_unavailable=True)

        assert local["video_url"] == "/files/tools/local.mp4?signed=1"
        assert local["outputs"]["video_url"] == local["video_url"]
        assert expired["video_url"] is None
        assert expired["outputs"]["video_url"] is None
        assert expired["status"] == WorkflowExecutionStatus.FAILED.value
        assert expired["error"] == "The generated video source has expired before local persistence."


class TestWorkflowRunHistoryQueries:
    def test_should_scope_page_to_installed_app_and_current_account(self) -> None:
        session = MagicMock()
        session.scalars.return_value = [_run()]

        page = WorkflowRunHistoryService.get_page(
            session=session,
            tenant_id="tenant-1",
            app_id="app-1",
            account_id="account-1",
            last_id=None,
            limit=20,
        )

        statement = str(session.scalars.call_args.args[0])
        assert "workflow_runs.tenant_id" in statement
        assert "workflow_runs.app_id" in statement
        assert "workflow_runs.created_by" in statement
        assert "workflow_app_logs.created_from" in statement
        assert "workflow_app_logs.created_by" in statement
        assert page.has_more is False
        assert page.last_id is None

    def test_should_return_next_cursor_when_page_has_more(self) -> None:
        session = MagicMock()
        session.scalars.return_value = [_run(id=f"run-{index}") for index in range(1, 4)]

        page = WorkflowRunHistoryService.get_page(
            session=session,
            tenant_id="tenant-1",
            app_id="app-1",
            account_id="account-1",
            last_id=None,
            limit=2,
        )

        assert [item["id"] for item in page.data] == ["run-1", "run-2"]
        assert page.has_more is True
        assert page.last_id == "run-2"

    def test_should_reject_cursor_outside_current_account_scope(self) -> None:
        session = MagicMock()
        session.execute.return_value.one_or_none.return_value = None

        with pytest.raises(ValueError, match="Invalid workflow run cursor"):
            WorkflowRunHistoryService.get_page(
                session=session,
                tenant_id="tenant-1",
                app_id="app-1",
                account_id="account-1",
                last_id="other-account-run",
                limit=20,
            )

    def test_should_return_none_when_detail_is_outside_scope(self) -> None:
        session = MagicMock()
        session.scalar.return_value = None

        detail = WorkflowRunHistoryService.get_detail(
            session=session,
            tenant_id="tenant-1",
            app_id="app-1",
            account_id="account-1",
            run_id="other-account-run",
        )

        statement = str(session.scalar.call_args.args[0])
        assert "workflow_runs.created_by" in statement
        assert "workflow_app_logs.created_by" in statement
        assert detail is None
