"""Historical generated-asset backfill with dry-run support.

The scan is intentionally limited to assistant ``MessageFile`` records and successful
workflow final outputs accepted by ``generated_asset_discovery``. Standalone historical
``ToolFile`` rows are excluded because their generation source cannot be proven.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from graphon.enums import WorkflowExecutionStatus
from graphon.file import FileTransferMethod
from models.enums import MessageFileBelongsTo
from models.model import MessageFile
from models.tools import ToolFile
from models.workflow import WorkflowRun
from services.generated_asset_discovery import extract_workflow_asset_candidates
from services.generated_file_service import (
    build_workflow_tool_file_candidates,
    generated_asset_exists,
    register_generated_asset_candidate,
    register_generated_file_from_message_file,
)

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class GeneratedAssetBackfillStats:
    """Flat counters printed by the generated asset backfill CLI."""

    scanned: int = 0
    created: int = 0
    skipped: int = 0
    errors: int = 0


def backfill_generated_assets(
    session: Session,
    *,
    dry_run: bool,
    batch_size: int = 200,
    tenant_id: str | None = None,
) -> GeneratedAssetBackfillStats:
    """Backfill known final assets while isolating malformed historical rows."""

    stats = GeneratedAssetBackfillStats()
    _backfill_message_files(session, stats, dry_run=dry_run, batch_size=batch_size, tenant_id=tenant_id)
    _backfill_workflow_assets(session, stats, dry_run=dry_run, batch_size=batch_size, tenant_id=tenant_id)
    if not dry_run:
        session.commit()
    return stats


def _backfill_message_files(
    session: Session,
    stats: GeneratedAssetBackfillStats,
    *,
    dry_run: bool,
    batch_size: int,
    tenant_id: str | None,
) -> None:
    stmt = (
        select(MessageFile)
        .join(ToolFile, ToolFile.id == MessageFile.upload_file_id)
        .where(MessageFile.transfer_method == FileTransferMethod.TOOL_FILE)
        .where(MessageFile.belongs_to == MessageFileBelongsTo.ASSISTANT)
        .order_by(MessageFile.created_at.asc())
        .execution_options(yield_per=batch_size)
    )
    if tenant_id:
        stmt = stmt.where(ToolFile.tenant_id == tenant_id)
    for message_file in session.scalars(stmt):
        stats.scanned += 1
        try:
            tool_file_id = str(message_file.upload_file_id) if message_file.upload_file_id else None
            if not tool_file_id:
                stats.skipped += 1
                continue
            exists = generated_asset_exists(session, tool_file_id=tool_file_id)
            if exists:
                if not dry_run:
                    with session.begin_nested():
                        register_generated_file_from_message_file(session, message_file)
                stats.skipped += 1
                continue
            if dry_run:
                stats.created += 1
                continue
            with session.begin_nested():
                if register_generated_file_from_message_file(session, message_file):
                    stats.created += 1
                else:
                    stats.skipped += 1
        except Exception:
            stats.errors += 1
            logger.exception("Failed to backfill MessageFile asset: message_file_id=%s", message_file.id)


def _backfill_workflow_assets(
    session: Session,
    stats: GeneratedAssetBackfillStats,
    *,
    dry_run: bool,
    batch_size: int,
    tenant_id: str | None,
) -> None:
    stmt = (
        select(WorkflowRun)
        .where(WorkflowRun.status == WorkflowExecutionStatus.SUCCEEDED)
        .order_by(WorkflowRun.created_at.asc())
        .execution_options(yield_per=batch_size)
    )
    if tenant_id:
        stmt = stmt.where(WorkflowRun.tenant_id == tenant_id)
    seen_source_keys: set[tuple[str, str]] = set()
    for workflow_run in session.scalars(stmt):
        candidates = [
            *extract_workflow_asset_candidates(workflow_run),
            *build_workflow_tool_file_candidates(session, workflow_run),
        ]
        for candidate in candidates:
            stats.scanned += 1
            try:
                candidate_identity = (candidate.tenant_id, candidate.source_key)
                if candidate_identity in seen_source_keys:
                    stats.skipped += 1
                    continue
                seen_source_keys.add(candidate_identity)
                if generated_asset_exists(session, source_key=candidate.source_key, tenant_id=candidate.tenant_id):
                    stats.skipped += 1
                    continue
                if dry_run:
                    stats.created += 1
                    continue
                with session.begin_nested():
                    _, created = register_generated_asset_candidate(session, candidate)
                    stats.created += int(created)
                    stats.skipped += int(not created)
            except Exception:
                stats.errors += 1
                logger.exception("Failed to backfill workflow asset: workflow_run_id=%s", workflow_run.id)
