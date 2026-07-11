"""CLI commands for generated content asset maintenance."""

from __future__ import annotations

import json
from pathlib import Path

import click

from extensions.ext_database import db
from libs.helper import uuid_value
from models.tools import GeneratedFile
from services.generated_asset_backfill_service import backfill_generated_assets
from services.generated_file_service import (
    mark_generated_video_source_unavailable,
    persist_generated_video_asset,
)


@click.command("backfill-generated-assets", help="Backfill local and trusted remote generated assets.")
@click.option(
    "--dry-run/--execute",
    default=True,
    show_default=True,
    help="Preview candidates or persist idempotent asset rows.",
)
@click.option("--batch-size", default=200, show_default=True, type=click.IntRange(min=1, max=5000))
@click.option("--tenant-id", default=None, help="Optionally restrict the scan to one tenant UUID.")
def backfill_generated_assets_command(dry_run: bool, batch_size: int, tenant_id: str | None) -> None:
    """Scan historical final outputs and print deterministic result counters."""

    if tenant_id:
        try:
            tenant_id = uuid_value(tenant_id)
        except ValueError as exc:
            raise click.BadParameter(str(exc), param_hint="--tenant-id") from exc

    stats = backfill_generated_assets(
        db.session,
        dry_run=dry_run,
        batch_size=batch_size,
        tenant_id=tenant_id,
    )
    click.echo(
        json.dumps(
            {
                "mode": "dry-run" if dry_run else "execute",
                "scanned": stats.scanned,
                "created": stats.created,
                "skipped": stats.skipped,
                "errors": stats.errors,
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    if stats.errors:
        raise click.ClickException(f"Generated asset backfill completed with {stats.errors} errors.")


@click.command("recover-generated-videos", help="Import rescued workflow videos into durable Dify storage.")
@click.option(
    "--source-dir",
    required=True,
    type=click.Path(exists=True, file_okay=False, path_type=Path),
    help="Directory containing <generated-asset-id>.mp4 rescue files.",
)
@click.option(
    "--mark-confirmed-unavailable/--keep-confirmed-remote",
    default=False,
    show_default=True,
    help="Mark assets with a matching <generated-asset-id>.unavailable marker as unavailable.",
)
@click.option("--dry-run/--execute", default=True, show_default=True)
def recover_generated_videos_command(
    source_dir: Path,
    mark_confirmed_unavailable: bool,
    dry_run: bool,
) -> None:
    """Promote verified rescue files and preserve explicit state for missing sources."""

    assets = list(
        db.session.scalars(
            db.select(GeneratedFile)
            .where(
                GeneratedFile.source_kind == "workflow_video",
                GeneratedFile.deleted_at.is_(None),
            )
            .order_by(GeneratedFile.created_at.desc())
        )
    )
    stats = {"scanned": len(assets), "persisted": 0, "unavailable": 0, "skipped": 0, "errors": 0}
    for asset in assets:
        if asset.storage_type == "tool_file" and asset.tool_file_id:
            stats["skipped"] += 1
            continue
        rescue_path = source_dir / f"{asset.id}.mp4"
        try:
            if rescue_path.is_file():
                if not dry_run:
                    persist_generated_video_asset(db.session, asset, file_binary=rescue_path.read_bytes())
                    db.session.commit()
                stats["persisted"] += 1
            elif mark_confirmed_unavailable and (source_dir / f"{asset.id}.unavailable").is_file():
                if not dry_run and mark_generated_video_source_unavailable(asset):
                    db.session.add(asset)
                    db.session.commit()
                stats["unavailable"] += 1
            else:
                stats["skipped"] += 1
        except Exception as exc:
            db.session.rollback()
            stats["errors"] += 1
            click.echo(f"asset_id={asset.id} error={exc}", err=True)

    click.echo(
        json.dumps(
            {"mode": "dry-run" if dry_run else "execute", **stats},
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    if stats["errors"]:
        raise click.ClickException(f"Generated video recovery completed with {stats['errors']} errors.")
