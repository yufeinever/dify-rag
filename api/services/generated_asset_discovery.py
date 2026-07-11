"""Trusted remote generated-asset discovery.

Only documented workflow output fields are inspected. User inputs and arbitrary text
URLs are never crawled, and every accepted remote URL must use HTTPS on an approved
asset host.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field
from datetime import datetime
from mimetypes import guess_type
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit, urlunsplit
from uuid import UUID

from graphon.enums import WorkflowExecutionStatus
from models.workflow import WorkflowRun

TRUSTED_REMOTE_ASSET_HOSTS = frozenset({"ai.meinmalzebier.shop", "vidgen.x.ai"})
SUCCESSFUL_BUSINESS_STATUSES = frozenset({"done", "succeeded"})
DIFY_FILE_IDENTITY = "__dify__file__"
TRUSTED_POSTER_APP_IDS = frozenset(
    {
        "13f7a06c-769d-474c-8863-613e9aeb25cb",
        "7bdc02f9-388b-4e9a-8191-9ca812528bdf",
    }
)

_POSTER_URL_RE = re.compile(
    r"https://ai\.meinmalzebier\.shop/poster-files/files/"
    r"(?P<stem>poster-[0-9a-fA-F-]{36})(?P<thumb>-thumb)?\.(?P<extension>png|jpg)"
    r"(?:\?[^\s\]\)<>\"']*)?"
)
_LEGACY_POSTER_URL_RE = re.compile(
    r"http://150\.5\.132\.104:8088/files/"
    r"(?P<stem>poster-[0-9a-fA-F-]{36})(?P<thumb>-thumb)?\.(?P<extension>png|jpg)"
    r"(?:\?[^\s\]\)<>\"']*)?"
)


@dataclass(frozen=True, slots=True)
class GeneratedAssetCandidate:
    """Validated metadata required to create one durable generated asset row."""

    tenant_id: str
    owner_user_id: str
    name: str
    mime_type: str
    file_type: str
    storage_type: str
    source_kind: str
    source_key: str
    tool_file_id: str | None = None
    source_url: str | None = None
    thumbnail_url: str | None = None
    source_app_id: str | None = None
    source_conversation_id: str | None = None
    source_message_id: str | None = None
    source_workflow_run_id: str | None = None
    size: int = -1
    asset_metadata: dict[str, Any] = field(default_factory=dict)
    created_at: datetime | None = None


def extract_workflow_asset_candidates(workflow_run: WorkflowRun) -> list[GeneratedAssetCandidate]:
    """Extract trusted final video and poster outputs from one workflow run."""

    status = workflow_run.status
    status_value = status.value if isinstance(status, WorkflowExecutionStatus) else str(status)
    if status_value != WorkflowExecutionStatus.SUCCEEDED.value:
        return []

    outputs = _json_object(workflow_run.outputs)
    business_status = _optional_string(outputs.get("status"))
    if business_status and business_status.lower() not in SUCCESSFUL_BUSINESS_STATUSES:
        return []

    candidates: list[GeneratedAssetCandidate] = []
    video_url = trusted_remote_asset_url(outputs.get("video_url"))
    if video_url:
        character_image_url = trusted_remote_asset_url(outputs.get("character_image_url"))
        scene_image_url = trusted_remote_asset_url(outputs.get("scene_image_url"))
        attachments = [
            {"kind": kind, "url": url}
            for kind, url in (
                ("character_image", character_image_url),
                ("scene_image", scene_image_url),
            )
            if url
        ]
        extension = _extension_from_url(video_url, default=".mp4")
        inputs = _json_object(workflow_run.inputs)
        title = (
            _optional_string(outputs.get("title"))
            or _markdown_title(_optional_string(outputs.get("result")) or "")
            or _first_input_request(inputs)
        )
        title = _safe_asset_title(title, fallback=f"video-{workflow_run.id}")
        candidates.append(
            GeneratedAssetCandidate(
                tenant_id=str(workflow_run.tenant_id),
                owner_user_id=str(workflow_run.created_by),
                name=f"{title}{extension}",
                mime_type=guess_type(f"file{extension}")[0] or "video/mp4",
                file_type="video",
                storage_type="remote_url",
                source_kind="workflow_video",
                source_key=remote_source_key(
                    "video",
                    video_url,
                    owner_user_id=str(workflow_run.created_by),
                    source_app_id=str(workflow_run.app_id),
                ),
                source_url=video_url,
                thumbnail_url=scene_image_url or character_image_url,
                source_app_id=str(workflow_run.app_id),
                source_workflow_run_id=str(workflow_run.id),
                asset_metadata={
                    "attachments": attachments,
                    "character_image_url": character_image_url,
                    "scene_image_url": scene_image_url,
                },
                created_at=workflow_run.created_at,
            )
        )

    answer = outputs.get("answer")
    if str(workflow_run.app_id) in TRUSTED_POSTER_APP_IDS and isinstance(answer, str):
        candidates.extend(_poster_candidates_from_answer(workflow_run, answer))
    return candidates


def extract_workflow_tool_file_ids(workflow_run: WorkflowRun) -> list[str]:
    """Extract only native Dify ToolFile references from successful final outputs."""

    status = workflow_run.status
    status_value = status.value if isinstance(status, WorkflowExecutionStatus) else str(status)
    if status_value != WorkflowExecutionStatus.SUCCEEDED.value:
        return []

    outputs = _json_object(workflow_run.outputs)
    business_status = _optional_string(outputs.get("status"))
    if business_status and business_status.lower() not in SUCCESSFUL_BUSINESS_STATUSES:
        return []

    tool_file_ids: list[str] = []
    seen: set[str] = set()
    for value in _walk_output_values(outputs):
        if not isinstance(value, dict):
            continue
        if value.get("dify_model_identity") != DIFY_FILE_IDENTITY:
            continue
        if value.get("transfer_method") != "tool_file":
            continue
        related_id = value.get("related_id")
        if not isinstance(related_id, str):
            continue
        try:
            tool_file_id = str(UUID(related_id))
        except ValueError:
            continue
        if tool_file_id not in seen:
            seen.add(tool_file_id)
            tool_file_ids.append(tool_file_id)
    return tool_file_ids


def trusted_remote_asset_url(value: Any) -> str | None:
    """Return an approved absolute HTTPS asset URL, otherwise ``None``."""

    if not isinstance(value, str):
        return None
    candidate = value.strip()
    if not candidate:
        return None
    parsed = urlsplit(candidate)
    if parsed.scheme != "https" or parsed.hostname not in TRUSTED_REMOTE_ASSET_HOSTS:
        return None
    if parsed.username or parsed.password or not parsed.path:
        return None
    return candidate


def remote_source_key(
    kind: str,
    url: str,
    *,
    owner_user_id: str = "",
    source_app_id: str = "",
) -> str:
    """Build a scoped, query-insensitive identity for one remote asset."""

    parsed = urlsplit(url)
    normalized = urlunsplit((parsed.scheme.lower(), parsed.netloc.lower(), parsed.path, "", ""))
    identity = "\n".join((kind, owner_user_id, source_app_id, normalized))
    digest = hashlib.sha256(identity.encode()).hexdigest()
    return f"remote:{kind}:{digest}"


def _poster_candidates_from_answer(workflow_run: WorkflowRun, answer: str) -> list[GeneratedAssetCandidate]:
    posters: dict[str, dict[str, str]] = {}
    for pattern in (_POSTER_URL_RE, _LEGACY_POSTER_URL_RE):
        for match in pattern.finditer(answer):
            url = _trusted_poster_url(match.group(0))
            if not url:
                continue
            item = posters.setdefault(match.group("stem"), {})
            item["thumbnail" if match.group("thumb") else "source"] = url

    candidates: list[GeneratedAssetCandidate] = []
    for stem, urls in posters.items():
        source_url = urls.get("source")
        if not source_url:
            continue
        candidates.append(
            GeneratedAssetCandidate(
                tenant_id=str(workflow_run.tenant_id),
                owner_user_id=str(workflow_run.created_by),
                name=f"{stem}.png",
                mime_type="image/png",
                file_type="image",
                storage_type="remote_url",
                source_kind="workflow_poster",
                source_key=remote_source_key(
                    "poster",
                    source_url,
                    owner_user_id=str(workflow_run.created_by),
                    source_app_id=str(workflow_run.app_id),
                ),
                source_url=source_url,
                thumbnail_url=urls.get("thumbnail"),
                source_app_id=str(workflow_run.app_id),
                source_workflow_run_id=str(workflow_run.id),
                asset_metadata={"output_field": "answer"},
                created_at=workflow_run.created_at,
            )
        )
    return candidates


def _trusted_poster_url(value: str) -> str | None:
    approved = trusted_remote_asset_url(value)
    if approved:
        return approved
    parsed = urlsplit(value.strip())
    if (
        parsed.scheme == "http"
        and parsed.hostname == "150.5.132.104"
        and parsed.port == 8088
        and parsed.username is None
        and parsed.password is None
        and re.fullmatch(r"/files/poster-[0-9a-fA-F-]{36}(?:-thumb)?\.(?:png|jpg)", parsed.path)
    ):
        filename = parsed.path.rsplit("/", 1)[-1]
        return f"https://ai.meinmalzebier.shop/poster-files/files/{filename}"
    return None


def _json_object(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return dict(value)
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
        except (TypeError, ValueError):
            return {}
        return dict(parsed) if isinstance(parsed, dict) else {}
    return {}


def _walk_output_values(value: Any):
    yield value
    if isinstance(value, dict):
        for item in value.values():
            yield from _walk_output_values(item)
    elif isinstance(value, list):
        for item in value:
            yield from _walk_output_values(item)


def _optional_string(value: Any) -> str | None:
    if value is None or isinstance(value, (dict, list)):
        return None
    text = str(value).strip()
    return text or None


def _safe_asset_title(value: Any, *, fallback: str) -> str:
    title = _optional_string(value) or fallback
    title = re.sub(r"[\\/:*?\"<>|]+", "-", title).strip(" .-")
    return (title or fallback)[:180]


def _markdown_title(markdown: str) -> str | None:
    for line in markdown.splitlines():
        if line.startswith("# "):
            return line[2:].strip() or None
    return None


def _first_input_request(inputs: dict[str, Any]) -> str | None:
    for key in ("video_request", "request", "query", "requirement"):
        value = _optional_string(inputs.get(key))
        if value:
            return value[:180]
    return None


def _extension_from_url(url: str, *, default: str) -> str:
    suffix = Path(urlsplit(url).path).suffix.lower()
    return suffix if 1 < len(suffix) <= 12 else default
