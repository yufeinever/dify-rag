from __future__ import annotations

import json
import sqlite3
import threading
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .models import CreateTeamArtifactRequest, ToolContext


def utc_now_iso() -> str:
    return datetime.now(UTC).isoformat()


class AuditStore:
    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path
        self._lock = threading.Lock()
        self._ensure_schema()

    def _connect(self) -> sqlite3.Connection:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(self.db_path)
        connection.row_factory = sqlite3.Row
        return connection

    def _ensure_schema(self) -> None:
        with self._lock, self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS audit_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    request_id TEXT NOT NULL,
                    tenant_id TEXT NOT NULL,
                    bot_id TEXT NOT NULL,
                    channel TEXT NOT NULL,
                    chat_type TEXT NOT NULL,
                    session_key TEXT NOT NULL,
                    actor_id TEXT NOT NULL,
                    tool TEXT NOT NULL,
                    status TEXT NOT NULL,
                    metadata TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS team_artifacts (
                    id TEXT PRIMARY KEY,
                    tenant_id TEXT NOT NULL,
                    bot_id TEXT NOT NULL,
                    channel TEXT NOT NULL,
                    chat_id TEXT,
                    owner_open_id TEXT,
                    artifact_type TEXT NOT NULL,
                    title TEXT NOT NULL,
                    content TEXT NOT NULL,
                    visibility TEXT NOT NULL,
                    source_request_id TEXT,
                    metadata TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS poster_deliveries (
                    job_id TEXT PRIMARY KEY,
                    channel TEXT NOT NULL,
                    chat_id TEXT,
                    sender_open_id TEXT,
                    session_id TEXT,
                    session_key TEXT,
                    status TEXT NOT NULL,
                    poster_url TEXT,
                    thumbnail_url TEXT,
                    image_key TEXT,
                    attempt_count INTEGER NOT NULL DEFAULT 0,
                    last_error TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    delivered_at TEXT
                )
                """
            )
            connection.execute("CREATE INDEX IF NOT EXISTS idx_audit_session ON audit_events(session_key, created_at)")
            connection.execute("CREATE INDEX IF NOT EXISTS idx_audit_request ON audit_events(request_id)")
            connection.execute("CREATE INDEX IF NOT EXISTS idx_artifact_context ON team_artifacts(tenant_id, bot_id, chat_id)")
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS artifact_deliveries (
                    artifact_id TEXT PRIMARY KEY,
                    job_id TEXT,
                    channel TEXT NOT NULL,
                    chat_id TEXT,
                    sender_open_id TEXT,
                    session_id TEXT,
                    session_key TEXT,
                    artifact_type TEXT NOT NULL,
                    filename TEXT,
                    mime_type TEXT,
                    file_url TEXT,
                    local_path TEXT,
                    resource_key TEXT,
                    status TEXT NOT NULL,
                    attempt_count INTEGER NOT NULL DEFAULT 0,
                    last_error TEXT,
                    metadata TEXT NOT NULL DEFAULT '{}',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    delivered_at TEXT
                )
                """
            )
            connection.execute("CREATE INDEX IF NOT EXISTS idx_poster_delivery_status ON poster_deliveries(status, updated_at)")
            connection.execute("CREATE INDEX IF NOT EXISTS idx_artifact_delivery_status ON artifact_deliveries(status, updated_at)")
            connection.execute("CREATE INDEX IF NOT EXISTS idx_artifact_delivery_job ON artifact_deliveries(job_id, channel)")

    def record_event(
        self,
        *,
        request_id: str,
        context: ToolContext,
        tool: str,
        status: str,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        with self._lock, self._connect() as connection:
            connection.execute(
                """
                INSERT INTO audit_events (
                    request_id, tenant_id, bot_id, channel, chat_type, session_key,
                    actor_id, tool, status, metadata, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    request_id,
                    context.tenant_id,
                    context.bot_id,
                    context.channel,
                    context.chat_type.value,
                    context.session_key,
                    context.actor_id,
                    tool,
                    status,
                    json.dumps(metadata or {}, ensure_ascii=False),
                    utc_now_iso(),
                ),
            )

    def create_artifact(self, request: CreateTeamArtifactRequest) -> dict[str, Any]:
        artifact_id = str(uuid.uuid4())
        created_at = utc_now_iso()
        context = request.context
        with self._lock, self._connect() as connection:
            connection.execute(
                """
                INSERT INTO team_artifacts (
                    id, tenant_id, bot_id, channel, chat_id, owner_open_id,
                    artifact_type, title, content, visibility, source_request_id,
                    metadata, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    artifact_id,
                    context.tenant_id,
                    context.bot_id,
                    context.channel,
                    context.chat_id,
                    context.actor_id,
                    request.artifact_type,
                    request.title,
                    request.content,
                    request.visibility,
                    request.source_request_id,
                    json.dumps(request.metadata, ensure_ascii=False),
                    created_at,
                ),
            )
        return {
            "artifact_id": artifact_id,
            "artifact_type": request.artifact_type,
            "title": request.title,
            "visibility": request.visibility,
            "created_at": created_at,
        }

    def list_events(self, *, limit: int = 100, session_key: str | None = None, tool: str | None = None) -> list[dict[str, Any]]:
        clauses: list[str] = []
        params: list[Any] = []
        if session_key:
            clauses.append("session_key = ?")
            params.append(session_key)
        if tool:
            clauses.append("tool = ?")
            params.append(tool)

        where_sql = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        params.append(limit)
        with self._lock, self._connect() as connection:
            rows = connection.execute(
                f"""
                SELECT request_id, tenant_id, bot_id, channel, chat_type, session_key,
                       actor_id, tool, status, metadata, created_at
                FROM audit_events
                {where_sql}
                ORDER BY id DESC
                LIMIT ?
                """,
                params,
            ).fetchall()
        events: list[dict[str, Any]] = []
        for row in rows:
            item = dict(row)
            item["metadata"] = json.loads(item["metadata"] or "{}")
            events.append(item)
        return events

    def register_poster_delivery(
        self,
        *,
        job_id: str,
        channel: str = "feishu",
        chat_id: str | None = None,
        sender_open_id: str | None = None,
        session_id: str | None = None,
        session_key: str | None = None,
        poster_url: str | None = None,
        thumbnail_url: str | None = None,
    ) -> dict[str, Any]:
        now = utc_now_iso()
        with self._lock, self._connect() as connection:
            connection.execute(
                """
                INSERT INTO poster_deliveries (
                    job_id, channel, chat_id, sender_open_id, session_id, session_key,
                    status, poster_url, thumbnail_url, created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(job_id) DO UPDATE SET
                    chat_id = COALESCE(excluded.chat_id, poster_deliveries.chat_id),
                    sender_open_id = COALESCE(excluded.sender_open_id, poster_deliveries.sender_open_id),
                    session_id = COALESCE(excluded.session_id, poster_deliveries.session_id),
                    session_key = COALESCE(excluded.session_key, poster_deliveries.session_key),
                    poster_url = COALESCE(excluded.poster_url, poster_deliveries.poster_url),
                    thumbnail_url = COALESCE(excluded.thumbnail_url, poster_deliveries.thumbnail_url),
                    status = CASE
                        WHEN poster_deliveries.status IN ('delivered', 'failed') THEN poster_deliveries.status
                        ELSE 'pending'
                    END,
                    updated_at = excluded.updated_at
                """,
                (
                    job_id,
                    channel,
                    chat_id,
                    sender_open_id,
                    session_id,
                    session_key,
                    "pending",
                    poster_url,
                    thumbnail_url,
                    now,
                    now,
                ),
            )
            return dict(connection.execute("SELECT * FROM poster_deliveries WHERE job_id = ?", (job_id,)).fetchone())

    def list_poster_deliveries(self, *, limit: int = 100, status: str | None = None) -> list[dict[str, Any]]:
        clauses: list[str] = []
        params: list[Any] = []
        if status:
            clauses.append("status = ?")
            params.append(status)
        params.append(limit)
        where_sql = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        with self._lock, self._connect() as connection:
            rows = connection.execute(
                f"""
                SELECT * FROM poster_deliveries
                {where_sql}
                ORDER BY updated_at DESC
                LIMIT ?
                """,
                params,
            ).fetchall()
        return [dict(row) for row in rows]

    def list_due_poster_deliveries(self, *, limit: int, max_attempts: int) -> list[dict[str, Any]]:
        with self._lock, self._connect() as connection:
            rows = connection.execute(
                """
                SELECT * FROM poster_deliveries
                WHERE status IN ('pending', 'running') AND attempt_count < ?
                ORDER BY updated_at ASC
                LIMIT ?
                """,
                (max_attempts, limit),
            ).fetchall()
        return [dict(row) for row in rows]

    def update_poster_delivery_target(
        self,
        job_id: str,
        *,
        chat_id: str | None = None,
        sender_open_id: str | None = None,
        session_id: str | None = None,
        session_key: str | None = None,
    ) -> None:
        now = utc_now_iso()
        with self._lock, self._connect() as connection:
            connection.execute(
                """
                UPDATE poster_deliveries
                SET chat_id = COALESCE(?, chat_id),
                    sender_open_id = COALESCE(?, sender_open_id),
                    session_id = COALESCE(?, session_id),
                    session_key = COALESCE(?, session_key),
                    updated_at = ?
                WHERE job_id = ?
                """,
                (chat_id, sender_open_id, session_id, session_key, now, job_id),
            )

    def mark_poster_delivery_attempt(self, job_id: str, *, status: str, error: str | None = None) -> None:
        now = utc_now_iso()
        with self._lock, self._connect() as connection:
            connection.execute(
                """
                UPDATE poster_deliveries
                SET status = ?, attempt_count = attempt_count + 1, last_error = ?, updated_at = ?
                WHERE job_id = ?
                """,
                (status, error, now, job_id),
            )

    def mark_poster_delivery_delivered(self, job_id: str, *, poster_url: str, image_key: str) -> None:
        now = utc_now_iso()
        with self._lock, self._connect() as connection:
            connection.execute(
                """
                UPDATE poster_deliveries
                SET status = 'delivered', poster_url = ?, image_key = ?, last_error = NULL,
                    updated_at = ?, delivered_at = ?
                WHERE job_id = ?
                """,
                (poster_url, image_key, now, now, job_id),
            )

    def mark_poster_delivery_terminal(
        self,
        job_id: str,
        *,
        status: str,
        error: str | None = None,
        poster_url: str | None = None,
        thumbnail_url: str | None = None,
    ) -> None:
        now = utc_now_iso()
        with self._lock, self._connect() as connection:
            connection.execute(
                """
                UPDATE poster_deliveries
                SET status = ?, poster_url = COALESCE(?, poster_url), thumbnail_url = COALESCE(?, thumbnail_url),
                    last_error = ?, updated_at = ?
                WHERE job_id = ?
                """,
                (status, poster_url, thumbnail_url, error, now, job_id),
            )

    def register_artifact_delivery(
        self,
        *,
        artifact_id: str | None = None,
        job_id: str | None = None,
        channel: str = "feishu",
        chat_id: str | None = None,
        sender_open_id: str | None = None,
        session_id: str | None = None,
        session_key: str | None = None,
        artifact_type: str,
        filename: str | None = None,
        mime_type: str | None = None,
        file_url: str | None = None,
        local_path: str | None = None,
        status: str = "pending",
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        now = utc_now_iso()
        artifact_id = artifact_id or str(uuid.uuid4())
        with self._lock, self._connect() as connection:
            connection.execute(
                """
                INSERT INTO artifact_deliveries (
                    artifact_id, job_id, channel, chat_id, sender_open_id, session_id, session_key,
                    artifact_type, filename, mime_type, file_url, local_path, status, metadata,
                    created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(artifact_id) DO UPDATE SET
                    job_id = COALESCE(excluded.job_id, artifact_deliveries.job_id),
                    chat_id = COALESCE(excluded.chat_id, artifact_deliveries.chat_id),
                    sender_open_id = COALESCE(excluded.sender_open_id, artifact_deliveries.sender_open_id),
                    session_id = COALESCE(excluded.session_id, artifact_deliveries.session_id),
                    session_key = COALESCE(excluded.session_key, artifact_deliveries.session_key),
                    filename = COALESCE(excluded.filename, artifact_deliveries.filename),
                    mime_type = COALESCE(excluded.mime_type, artifact_deliveries.mime_type),
                    file_url = COALESCE(excluded.file_url, artifact_deliveries.file_url),
                    local_path = COALESCE(excluded.local_path, artifact_deliveries.local_path),
                    status = CASE
                        WHEN artifact_deliveries.status IN ('delivered', 'failed') THEN artifact_deliveries.status
                        ELSE excluded.status
                    END,
                    metadata = excluded.metadata,
                    updated_at = excluded.updated_at
                """,
                (
                    artifact_id,
                    job_id,
                    channel,
                    chat_id,
                    sender_open_id,
                    session_id,
                    session_key,
                    artifact_type,
                    filename,
                    mime_type,
                    file_url,
                    local_path,
                    status,
                    json.dumps(metadata or {}, ensure_ascii=False),
                    now,
                    now,
                ),
            )
            return dict(connection.execute("SELECT * FROM artifact_deliveries WHERE artifact_id = ?", (artifact_id,)).fetchone())

    def get_artifact_delivery(self, artifact_id: str) -> dict[str, Any] | None:
        with self._lock, self._connect() as connection:
            row = connection.execute("SELECT * FROM artifact_deliveries WHERE artifact_id = ?", (artifact_id,)).fetchone()
        return dict(row) if row else None

    def list_artifact_deliveries(self, *, limit: int = 100, status: str | None = None) -> list[dict[str, Any]]:
        clauses: list[str] = []
        params: list[Any] = []
        if status:
            clauses.append("status = ?")
            params.append(status)
        params.append(limit)
        where_sql = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        with self._lock, self._connect() as connection:
            rows = connection.execute(
                f"""
                SELECT * FROM artifact_deliveries
                {where_sql}
                ORDER BY updated_at DESC
                LIMIT ?
                """,
                params,
            ).fetchall()
        return [dict(row) for row in rows]

    def list_due_artifact_deliveries(self, *, limit: int, max_attempts: int) -> list[dict[str, Any]]:
        with self._lock, self._connect() as connection:
            rows = connection.execute(
                """
                SELECT * FROM artifact_deliveries
                WHERE status IN ('pending', 'running') AND attempt_count < ?
                ORDER BY updated_at ASC
                LIMIT ?
                """,
                (max_attempts, limit),
            ).fetchall()
        return [dict(row) for row in rows]

    def update_artifact_delivery_target(self, artifact_id: str, *, chat_id: str | None = None, sender_open_id: str | None = None, session_id: str | None = None, session_key: str | None = None) -> None:
        now = utc_now_iso()
        with self._lock, self._connect() as connection:
            connection.execute(
                """
                UPDATE artifact_deliveries
                SET chat_id = COALESCE(?, chat_id), sender_open_id = COALESCE(?, sender_open_id),
                    session_id = COALESCE(?, session_id), session_key = COALESCE(?, session_key), updated_at = ?
                WHERE artifact_id = ?
                """,
                (chat_id, sender_open_id, session_id, session_key, now, artifact_id),
            )

    def mark_artifact_delivery_attempt(self, artifact_id: str, *, status: str, error: str | None = None) -> None:
        now = utc_now_iso()
        with self._lock, self._connect() as connection:
            connection.execute(
                """
                UPDATE artifact_deliveries
                SET status = ?, attempt_count = attempt_count + 1, last_error = ?, updated_at = ?
                WHERE artifact_id = ?
                """,
                (status, error, now, artifact_id),
            )

    def mark_artifact_delivery_delivered(self, artifact_id: str, *, resource_key: str | None = None, file_url: str | None = None) -> None:
        now = utc_now_iso()
        with self._lock, self._connect() as connection:
            connection.execute(
                """
                UPDATE artifact_deliveries
                SET status = 'delivered', resource_key = COALESCE(?, resource_key), file_url = COALESCE(?, file_url),
                    last_error = NULL, updated_at = ?, delivered_at = ?
                WHERE artifact_id = ?
                """,
                (resource_key, file_url, now, now, artifact_id),
            )

    def mark_artifact_delivery_terminal(self, artifact_id: str, *, status: str, error: str | None = None, file_url: str | None = None) -> None:
        now = utc_now_iso()
        with self._lock, self._connect() as connection:
            connection.execute(
                """
                UPDATE artifact_deliveries
                SET status = ?, file_url = COALESCE(?, file_url), last_error = ?, updated_at = ?
                WHERE artifact_id = ?
                """,
                (status, file_url, error, now, artifact_id),
            )
