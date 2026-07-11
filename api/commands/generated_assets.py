"""CLI commands for generated content asset maintenance."""

from __future__ import annotations

import json

import click

from extensions.ext_database import db
from libs.helper import uuid_value
from services.generated_asset_backfill_service import backfill_generated_assets


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
