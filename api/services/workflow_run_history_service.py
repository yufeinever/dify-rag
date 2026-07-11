"""Account-scoped installed workflow run history.

This service intentionally reads the existing workflow run and application log tables.
Every query is scoped by tenant, app, installed-app source, account role, and account ID;
callers must not loosen those predicates based on request parameters.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from typing import Any, NotRequired, TypedDict

from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session

from graphon.enums import WorkflowExecutionStatus
from models.enums import CreatorUserRole
from models.tools import GeneratedFile
from models.workflow import WorkflowAppLog, WorkflowAppLogCreatedFrom, WorkflowRun
from services.generated_file_service import build_generated_file_preview_config


class WorkflowRunHistoryItem(TypedDict):
    id: str
    status: str
    request: str
    created_at: datetime
    finished_at: datetime | None
    elapsed_time: float
    duration: str | None
    aspect_ratio: str | None
    resolution: str | None
    error: str | None
    video_url: str | None
    character_image_url: str | None
    scene_image_url: str | None


class WorkflowRunHistoryDetail(WorkflowRunHistoryItem):
    inputs: dict[str, Any]
    outputs: dict[str, Any]
    result: str
    script: str
    storyboard: str
    title: NotRequired[str]
    intent: NotRequired[str]


@dataclass(frozen=True)
class WorkflowRunHistoryPage:
    data: list[WorkflowRunHistoryItem]
    has_more: bool
    last_id: str | None


class WorkflowRunHistoryService:
    """Read installed-app workflow runs that belong to one console account."""

    _MISSING_VIDEO_ERROR = "The workflow succeeded but did not return a playable video URL."
    _EXPIRED_VIDEO_ERROR = "The generated video source has expired before local persistence."

    @classmethod
    def get_page(
        cls,
        *,
        session: Session,
        tenant_id: str,
        app_id: str,
        account_id: str,
        last_id: str | None,
        limit: int,
    ) -> WorkflowRunHistoryPage:
        """Return a stable newest-first cursor page without exposing large workflow payloads.

        ``last_id`` is resolved through the same account-scoped predicate as the result query,
        so another account's run cannot be used as a cursor or leak its timestamp.
        """
        scope = cls._scope(tenant_id=tenant_id, app_id=app_id, account_id=account_id)
        stmt = select(WorkflowRun).join(WorkflowAppLog, WorkflowAppLog.workflow_run_id == WorkflowRun.id).where(*scope)

        if last_id:
            cursor_stmt = (
                select(WorkflowRun.created_at, WorkflowRun.id)
                .join(WorkflowAppLog, WorkflowAppLog.workflow_run_id == WorkflowRun.id)
                .where(*scope, WorkflowRun.id == last_id)
                .limit(1)
            )
            cursor = session.execute(cursor_stmt).one_or_none()
            if cursor is None:
                raise ValueError("Invalid workflow run cursor")
            stmt = stmt.where(
                or_(
                    WorkflowRun.created_at < cursor.created_at,
                    and_(WorkflowRun.created_at == cursor.created_at, WorkflowRun.id < cursor.id),
                )
            )

        runs = list(
            session.scalars(stmt.order_by(WorkflowRun.created_at.desc(), WorkflowRun.id.desc()).limit(limit + 1))
        )
        has_more = len(runs) > limit
        page_runs = runs[:limit]
        local_urls, unavailable_runs = cls._local_video_state(session, page_runs)
        return WorkflowRunHistoryPage(
            data=[cls.to_list_item(run, local_urls.get(run.id), run.id in unavailable_runs) for run in page_runs],
            has_more=has_more,
            last_id=page_runs[-1].id if has_more and page_runs else None,
        )

    @classmethod
    def get_detail(
        cls,
        *,
        session: Session,
        tenant_id: str,
        app_id: str,
        account_id: str,
        run_id: str,
    ) -> WorkflowRunHistoryDetail | None:
        """Return one account-owned installed-app run, or ``None`` for every out-of-scope ID."""
        stmt = (
            select(WorkflowRun)
            .join(WorkflowAppLog, WorkflowAppLog.workflow_run_id == WorkflowRun.id)
            .where(
                *cls._scope(tenant_id=tenant_id, app_id=app_id, account_id=account_id),
                WorkflowRun.id == run_id,
            )
            .limit(1)
        )
        run = session.scalar(stmt)
        if not run:
            return None
        local_urls, unavailable_runs = cls._local_video_state(session, [run])
        return cls.to_detail(run, local_urls.get(run.id), run.id in unavailable_runs)

    @staticmethod
    def _scope(*, tenant_id: str, app_id: str, account_id: str) -> tuple[Any, ...]:
        return (
            WorkflowRun.tenant_id == tenant_id,
            WorkflowRun.app_id == app_id,
            WorkflowRun.created_by_role == CreatorUserRole.ACCOUNT,
            WorkflowRun.created_by == account_id,
            WorkflowAppLog.tenant_id == tenant_id,
            WorkflowAppLog.app_id == app_id,
            WorkflowAppLog.created_from == WorkflowAppLogCreatedFrom.INSTALLED_APP,
            WorkflowAppLog.created_by_role == CreatorUserRole.ACCOUNT,
            WorkflowAppLog.created_by == account_id,
        )

    @classmethod
    def to_list_item(
        cls, run: WorkflowRun, local_video_url: str | None = None, video_unavailable: bool = False
    ) -> WorkflowRunHistoryItem:
        inputs = cls._run_payload(run, "inputs")
        outputs = cls._run_payload(run, "outputs")
        remote_video_url = cls._public_url(outputs.get("video_url"))
        video_url = None if video_unavailable else (local_video_url or remote_video_url)
        status_outputs = {**outputs, "video_url": video_url}
        status, error = cls._effective_status(run.status, run.error, status_outputs)
        if video_unavailable and status == WorkflowExecutionStatus.FAILED.value:
            error = run.error or cls._EXPIRED_VIDEO_ERROR
        return WorkflowRunHistoryItem(
            id=run.id,
            status=status,
            request=cls._first_string(inputs, "video_request", "request", "query", "requirement"),
            created_at=run.created_at,
            finished_at=run.finished_at,
            elapsed_time=run.elapsed_time,
            duration=cls._first_optional_string(inputs, "duration", "video_duration"),
            aspect_ratio=cls._first_optional_string(inputs, "aspect_ratio", "ratio"),
            resolution=cls._first_optional_string(inputs, "resolution"),
            error=error,
            video_url=video_url,
            character_image_url=cls._public_url(outputs.get("character_image_url")),
            scene_image_url=cls._public_url(outputs.get("scene_image_url")),
        )

    @classmethod
    def to_detail(
        cls, run: WorkflowRun, local_video_url: str | None = None, video_unavailable: bool = False
    ) -> WorkflowRunHistoryDetail:
        inputs = cls._run_payload(run, "inputs")
        outputs = cls._run_payload(run, "outputs")
        if local_video_url or video_unavailable:
            outputs["video_url"] = None if video_unavailable else local_video_url
        detail = WorkflowRunHistoryDetail(
            **cls.to_list_item(run, local_video_url, video_unavailable),
            inputs=inputs,
            outputs=outputs,
            result=cls._first_string(outputs, "result"),
            script=cls._first_string(outputs, "script"),
            storyboard=cls._first_string(outputs, "storyboard"),
        )
        title = cls._first_optional_string(outputs, "title") or cls._markdown_title(detail["result"])
        intent = cls._first_optional_string(outputs, "intent", "creative_intent") or cls._markdown_intent(
            detail["result"]
        )
        if title:
            detail["title"] = title
        if intent:
            detail["intent"] = intent
        return detail

    @classmethod
    def _local_video_state(cls, session: Session, runs: list[WorkflowRun]) -> tuple[dict[str, str], set[str]]:
        run_ids = [str(run.id) for run in runs]
        if not run_ids:
            return {}, set()
        assets = list(
            session.execute(
                select(GeneratedFile).where(
                    GeneratedFile.source_workflow_run_id.in_(run_ids),
                    GeneratedFile.source_kind == "workflow_video",
                    GeneratedFile.deleted_at.is_(None),
                )
            )
            .scalars()
            .all()
        )
        local_urls: dict[str, str] = {}
        unavailable_runs: set[str] = set()
        for asset in assets:
            run_id = str(asset.source_workflow_run_id)
            if asset.storage_type == "tool_file" and asset.tool_file_id:
                preview_url = cls._public_url(build_generated_file_preview_config(asset).get("preview_url"))
                if preview_url:
                    local_urls[run_id] = preview_url
            elif (asset.asset_metadata or {}).get("source_unavailable"):
                unavailable_runs.add(run_id)
        return local_urls, unavailable_runs

    @classmethod
    def _effective_status(
        cls,
        status: WorkflowExecutionStatus | str,
        error: str | None,
        outputs: dict[str, Any],
    ) -> tuple[str, str | None]:
        status_value = status.value if isinstance(status, WorkflowExecutionStatus) else str(status)
        if (
            status_value == WorkflowExecutionStatus.SUCCEEDED.value
            and cls._public_url(outputs.get("video_url")) is None
        ):
            return WorkflowExecutionStatus.FAILED.value, error or cls._MISSING_VIDEO_ERROR
        return status_value, error

    @staticmethod
    def _json_object(value: Any) -> dict[str, Any]:
        return dict(value) if isinstance(value, dict) else {}

    @classmethod
    def _run_payload(cls, run: WorkflowRun, field: str) -> dict[str, Any]:
        raw_value = getattr(run, field, None)
        if isinstance(raw_value, str):
            try:
                return cls._json_object(json.loads(raw_value))
            except (TypeError, ValueError):
                return {}
        return cls._json_object(getattr(run, f"{field}_dict", {}))

    @classmethod
    def _first_string(cls, values: dict[str, Any], *keys: str) -> str:
        return cls._first_optional_string(values, *keys) or ""

    @staticmethod
    def _first_optional_string(values: dict[str, Any], *keys: str) -> str | None:
        for key in keys:
            value = values.get(key)
            if value is not None and not isinstance(value, (dict, list)):
                text = str(value).strip()
                if text:
                    return text
        return None

    @staticmethod
    def _public_url(value: Any) -> str | None:
        if not isinstance(value, str):
            return None
        candidate = value.strip()
        if candidate.startswith(("https://", "http://", "/")):
            return candidate
        return None

    @staticmethod
    def _markdown_title(markdown: str) -> str | None:
        for line in markdown.splitlines():
            if line.startswith("# "):
                return line[2:].strip() or None
        return None

    @staticmethod
    def _markdown_intent(markdown: str) -> str | None:
        prefixes = ("**创作意图**：", "**创作意图**:", "**Creative intent**:")
        for line in markdown.splitlines():
            for prefix in prefixes:
                if line.startswith(prefix):
                    return line.removeprefix(prefix).strip() or None
        return None
