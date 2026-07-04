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
            connection.execute("CREATE INDEX IF NOT EXISTS idx_audit_session ON audit_events(session_key, created_at)")
            connection.execute("CREATE INDEX IF NOT EXISTS idx_audit_request ON audit_events(request_id)")
            connection.execute("CREATE INDEX IF NOT EXISTS idx_artifact_context ON team_artifacts(tenant_id, bot_id, chat_id)")

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
