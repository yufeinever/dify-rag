from __future__ import annotations

import asyncio
import json
import logging
import sqlite3
import time
from pathlib import Path
from urllib.parse import unquote, urlsplit
from typing import Any

import httpx

from .audit import AuditStore
from .clients import ServiceClients
from .config import Settings

logger = logging.getLogger(__name__)


def _base_url(value: object) -> str:
    return str(value).rstrip("/")


def _filename_from_url(url: str) -> str:
    path = urlsplit(url).path
    return unquote(path.rsplit("/", 1)[-1]) or "artifact.bin"


def _feishu_file_type(filename: str, mime_type: str) -> str:
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if ext in {"ppt", "pptx"}:
        return "ppt"
    if ext in {"doc", "docx"}:
        return "doc"
    if ext in {"xls", "xlsx", "csv"}:
        return "xls"
    if ext == "pdf" or mime_type == "application/pdf":
        return "pdf"
    return "stream"


def resolve_delivery_target_from_hermes(
    state_db_path: Path | None,
    lookup_id: str,
    *,
    session_id: str | None = None,
) -> dict[str, str | None]:
    if not state_db_path or not state_db_path.exists():
        return {}
    connection: sqlite3.Connection | None = None
    try:
        connection = sqlite3.connect(f"file:{state_db_path}?mode=ro", uri=True)
        connection.row_factory = sqlite3.Row
        if session_id:
            session = connection.execute(
                """
                SELECT id, user_id, session_key, chat_id
                FROM sessions
                WHERE id = ? AND source = 'feishu' AND chat_id IS NOT NULL
                LIMIT 1
                """,
                (session_id,),
            ).fetchone()
        else:
            message = connection.execute(
                """
                SELECT session_id
                FROM messages
                WHERE (content LIKE ? OR tool_calls LIKE ?)
                ORDER BY id DESC
                LIMIT 1
                """,
                (f"%{lookup_id}%", f"%{lookup_id}%"),
            ).fetchone()
            session = None
            if message:
                session = connection.execute(
                    """
                    SELECT id, user_id, session_key, chat_id
                    FROM sessions
                    WHERE id = ? AND source = 'feishu' AND chat_id IS NOT NULL
                    LIMIT 1
                    """,
                    (message["session_id"],),
                ).fetchone()
        if not session:
            return {}
        return {
            "session_id": session["id"],
            "sender_open_id": session["user_id"],
            "session_key": session["session_key"],
            "chat_id": session["chat_id"],
        }
    except sqlite3.Error as exc:
        logger.warning("resolve delivery target failed", extra={"lookup_id": lookup_id, "error": str(exc)})
        return {}
    finally:
        if connection is not None:
            connection.close()


class FeishuDeliveryClient:
    def __init__(self, settings: Settings) -> None:
        if not settings.feishu_app_id or not settings.feishu_app_secret:
            raise ValueError("FEISHU_APP_ID and FEISHU_APP_SECRET are required for poster delivery")
        self.settings = settings
        self._token: str | None = None
        self._token_expires_at = 0.0

    async def _tenant_access_token(self, client: httpx.AsyncClient) -> str:
        if self._token and time.time() < self._token_expires_at - 60:
            return self._token
        response = await client.post(
            f"{_base_url(self.settings.feishu_api_base_url)}/auth/v3/tenant_access_token/internal",
            json={"app_id": self.settings.feishu_app_id, "app_secret": self.settings.feishu_app_secret},
        )
        data = self._checked_json(response, "get tenant_access_token")
        token = data.get("tenant_access_token")
        if not isinstance(token, str) or not token:
            raise RuntimeError("Feishu tenant_access_token response did not include tenant_access_token")
        expire = data.get("expire")
        self._token = token
        self._token_expires_at = time.time() + float(expire if isinstance(expire, (int, float)) else 7200)
        return token

    async def send_text(self, chat_id: str, text: str) -> None:
        timeout = httpx.Timeout(self.settings.http_timeout_seconds)
        async with httpx.AsyncClient(timeout=timeout) as client:
            token = await self._tenant_access_token(client)
            response = await client.post(
                f"{_base_url(self.settings.feishu_api_base_url)}/im/v1/messages",
                params={"receive_id_type": "chat_id"},
                headers={"Authorization": f"Bearer {token}"},
                json={
                    "receive_id": chat_id,
                    "msg_type": "text",
                    "content": json.dumps({"text": text[:7000]}, ensure_ascii=False),
                },
            )
            self._checked_json(response, "send Feishu text")

    async def send_image_from_url(self, chat_id: str, image_url: str) -> str:
        timeout = httpx.Timeout(self.settings.http_timeout_seconds)
        async with httpx.AsyncClient(timeout=timeout) as client:
            image_response = await client.get(image_url)
            if image_response.status_code >= 400:
                raise RuntimeError(f"download poster image failed: {image_response.status_code} {image_response.text[:300]}")
            content_type = image_response.headers.get("content-type") or "image/png"
            suffix = ".jpg" if "jpeg" in content_type else ".png"
            token = await self._tenant_access_token(client)
            upload_response = await client.post(
                f"{_base_url(self.settings.feishu_api_base_url)}/im/v1/images",
                headers={"Authorization": f"Bearer {token}"},
                data={"image_type": "message"},
                files={"image": (f"poster{suffix}", image_response.content, content_type)},
            )
            upload_data = self._checked_json(upload_response, "upload Feishu image")
            image_key = (upload_data.get("data") or {}).get("image_key")
            if not isinstance(image_key, str) or not image_key:
                raise RuntimeError("Feishu image upload did not return image_key")
            send_response = await client.post(
                f"{_base_url(self.settings.feishu_api_base_url)}/im/v1/messages",
                params={"receive_id_type": "chat_id"},
                headers={"Authorization": f"Bearer {token}"},
                json={
                    "receive_id": chat_id,
                    "msg_type": "image",
                    "content": json.dumps({"image_key": image_key}, ensure_ascii=False),
                },
            )
            self._checked_json(send_response, "send Feishu image")
            return image_key


    async def send_file_from_url(self, chat_id: str, file_url: str, *, filename: str | None = None, mime_type: str | None = None) -> str:
        timeout = httpx.Timeout(self.settings.http_timeout_seconds)
        async with httpx.AsyncClient(timeout=timeout) as client:
            file_response = await client.get(file_url)
            if file_response.status_code >= 400:
                raise RuntimeError(f"download artifact file failed: {file_response.status_code} {file_response.text[:300]}")
            upload_name = filename or _filename_from_url(file_url)
            content_type = mime_type or file_response.headers.get("content-type") or "application/octet-stream"
            token = await self._tenant_access_token(client)
            upload_response = await client.post(
                f"{_base_url(self.settings.feishu_api_base_url)}/im/v1/files",
                headers={"Authorization": f"Bearer {token}"},
                data={"file_type": _feishu_file_type(upload_name, content_type), "file_name": upload_name},
                files={"file": (upload_name, file_response.content, content_type)},
            )
            upload_data = self._checked_json(upload_response, "upload Feishu file")
            file_key = (upload_data.get("data") or {}).get("file_key")
            if not isinstance(file_key, str) or not file_key:
                raise RuntimeError("Feishu file upload did not return file_key")
            send_response = await client.post(
                f"{_base_url(self.settings.feishu_api_base_url)}/im/v1/messages",
                params={"receive_id_type": "chat_id"},
                headers={"Authorization": f"Bearer {token}"},
                json={"receive_id": chat_id, "msg_type": "file", "content": json.dumps({"file_key": file_key}, ensure_ascii=False)},
            )
            self._checked_json(send_response, "send Feishu file")
            return file_key

    @staticmethod
    def _checked_json(response: httpx.Response, action: str) -> dict[str, Any]:
        if response.status_code >= 400:
            raise RuntimeError(f"{action} failed: {response.status_code} {response.text[:500]}")
        try:
            data = response.json()
        except ValueError as exc:
            raise RuntimeError(f"{action} returned non-json response") from exc
        if isinstance(data, dict) and data.get("code", 0) not in (0, "0"):
            raise RuntimeError(f"{action} failed: {data.get('code')} {data.get('msg') or data}")
        if not isinstance(data, dict):
            raise RuntimeError(f"{action} returned unexpected response")
        return data


class PosterDeliveryWorker:
    def __init__(
        self,
        *,
        settings: Settings,
        store: AuditStore,
        clients: ServiceClients,
        feishu: FeishuDeliveryClient | None,
    ) -> None:
        self.settings = settings
        self.store = store
        self.clients = clients
        self.feishu = feishu

    async def run_forever(self) -> None:
        while True:
            try:
                await self.run_once()
            except Exception:
                logger.exception("poster delivery worker tick failed")
            await asyncio.sleep(self.settings.poster_delivery_poll_interval_seconds)

    async def run_once(self) -> None:
        if not self.feishu:
            return
        artifact_rows = self.store.list_due_artifact_deliveries(
            limit=self.settings.poster_delivery_batch_size,
            max_attempts=self.settings.poster_delivery_max_attempts,
        )
        for row in artifact_rows:
            await self._process_artifact(row)

        rows = self.store.list_due_poster_deliveries(
            limit=self.settings.poster_delivery_batch_size,
            max_attempts=self.settings.poster_delivery_max_attempts,
        )
        for row in rows:
            if self.store.get_artifact_delivery(f"poster:{row['job_id']}"):
                continue
            await self._process(row)

    async def _process_artifact(self, row: dict[str, Any]) -> None:
        artifact_id = row["artifact_id"]
        job_id = row.get("job_id")
        try:
            chat_id = row.get("chat_id")
            if not chat_id:
                lookup_id = job_id or artifact_id
                target = resolve_delivery_target_from_hermes(self.settings.hermes_state_db_path, lookup_id, session_id=row.get("session_id"))
                chat_id = target.get("chat_id")
                if chat_id:
                    self.store.update_artifact_delivery_target(
                        artifact_id,
                        chat_id=chat_id,
                        sender_open_id=target.get("sender_open_id"),
                        session_id=target.get("session_id"),
                        session_key=target.get("session_key"),
                    )
                else:
                    self.store.mark_artifact_delivery_attempt(artifact_id, status="pending", error="missing Feishu chat_id")
                    if int(row.get("attempt_count") or 0) + 1 >= self.settings.poster_delivery_max_attempts:
                        self.store.mark_artifact_delivery_terminal(artifact_id, status="blocked_missing_target", error="missing Feishu chat_id")
                    return

            artifact_type = str(row.get("artifact_type") or "file")
            file_url = row.get("file_url")
            filename = row.get("filename")
            mime_type = row.get("mime_type")

            if artifact_type in {"poster", "image"} and job_id and not file_url:
                job = await self.clients.get_poster_job(job_id)
                status = job.get("status")
                poster_url = job.get("poster_url")
                thumbnail_url = job.get("thumbnail_url")
                if status == "succeeded" and isinstance(poster_url, str) and poster_url:
                    image_key = await self.feishu.send_image_from_url(chat_id, poster_url)
                    self.store.mark_artifact_delivery_delivered(artifact_id, file_url=poster_url, resource_key=image_key)
                    self.store.mark_poster_delivery_delivered(job_id, poster_url=poster_url, image_key=image_key)
                    return
                if status == "failed":
                    error = str(job.get("error") or "未知错误")
                    await self.feishu.send_text(chat_id, f"海报生成失败，任务 ID：{job_id}\n原因：{error}")
                    self.store.mark_artifact_delivery_terminal(artifact_id, status="failed", error=error, file_url=poster_url)
                    self.store.mark_poster_delivery_terminal(job_id, status="failed", error=error, poster_url=poster_url, thumbnail_url=thumbnail_url)
                    return
                self.store.mark_artifact_delivery_attempt(artifact_id, status="running", error=None)
                return

            if not isinstance(file_url, str) or not file_url:
                error = "generated artifact did not include a downloadable file_url"
                await self.feishu.send_text(chat_id, f"产物暂时无法自动回传，追踪 ID：{artifact_id}\n原因：生成工具没有返回可下载文件地址。")
                self.store.mark_artifact_delivery_terminal(artifact_id, status="blocked_missing_file", error=error)
                return

            if artifact_type in {"poster", "image"}:
                resource_key = await self.feishu.send_image_from_url(chat_id, file_url)
            else:
                resource_key = await self.feishu.send_file_from_url(chat_id, file_url, filename=filename, mime_type=mime_type)
            self.store.mark_artifact_delivery_delivered(artifact_id, file_url=file_url, resource_key=resource_key)
        except Exception as exc:
            self.store.mark_artifact_delivery_attempt(artifact_id, status="running", error=str(exc))
            logger.warning("artifact delivery failed", extra={"artifact_id": artifact_id, "error": str(exc)})

    async def _process(self, row: dict[str, Any]) -> None:
        job_id = row["job_id"]
        try:
            chat_id = row.get("chat_id")
            if not chat_id:
                target = resolve_delivery_target_from_hermes(self.settings.hermes_state_db_path, job_id, session_id=row.get("session_id"))
                chat_id = target.get("chat_id")
                if chat_id:
                    self.store.update_poster_delivery_target(
                        job_id,
                        chat_id=chat_id,
                        sender_open_id=target.get("sender_open_id"),
                        session_id=target.get("session_id"),
                        session_key=target.get("session_key"),
                    )
                else:
                    self.store.mark_poster_delivery_attempt(job_id, status="pending", error="missing Feishu chat_id")
                    if int(row.get("attempt_count") or 0) + 1 >= self.settings.poster_delivery_max_attempts:
                        self.store.mark_poster_delivery_terminal(job_id, status="blocked_missing_target", error="missing Feishu chat_id")
                    return

            job = await self.clients.get_poster_job(job_id)
            status = job.get("status")
            poster_url = job.get("poster_url")
            thumbnail_url = job.get("thumbnail_url")
            if status == "succeeded" and isinstance(poster_url, str) and poster_url:
                image_key = await self.feishu.send_image_from_url(chat_id, poster_url)
                self.store.mark_poster_delivery_delivered(job_id, poster_url=poster_url, image_key=image_key)
                return
            if status == "failed":
                error = str(job.get("error") or "未知错误")
                await self.feishu.send_text(chat_id, f"海报生成失败，任务 ID：{job_id}\n原因：{error}")
                self.store.mark_poster_delivery_terminal(job_id, status="failed", error=error, poster_url=poster_url, thumbnail_url=thumbnail_url)
                return
            self.store.mark_poster_delivery_attempt(job_id, status="running", error=None)
        except Exception as exc:
            self.store.mark_poster_delivery_attempt(job_id, status="running", error=str(exc))
            logger.warning("poster delivery failed", extra={"job_id": job_id, "error": str(exc)})
