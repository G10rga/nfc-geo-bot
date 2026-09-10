from __future__ import annotations

import sys
import time

import click

from config import Settings
from maps_client import NO_PHONE, MapsClient
from sheets_client import SheetsClient


def _clients() -> tuple[MapsClient, SheetsClient, Settings]:
    settings = Settings.from_env()
    maps = MapsClient(headless=settings.headless)
    sheets = SheetsClient(
        settings.oauth_credentials_file,
        settings.oauth_token_file,
        settings.sheet_id,
        settings.sheet_tab,
    )
    return maps, sheets, settings


@click.group()
def cli() -> None:
    """NFC Geo bot — look up businesses on Google Maps and fill your Sheet."""


@cli.command("add")
@click.argument("name")
@click.option(
    "--location",
    "-l",
    default="",
    help="City hint for search (e.g. Tbilisi). District is filled automatically.",
)
@click.option("--dry-run", is_flag=True, help="Print result without writing to Sheet")
@click.option(
    "--show-browser",
    is_flag=True,
    help="Show the browser window (useful if Maps blocks headless)",
)
def add_business(name: str, location: str, dry_run: bool, show_browser: bool) -> None:
    """Search Maps and append one row to the spreadsheet."""
    maps, sheets, settings = _clients()
    if show_browser:
        maps = MapsClient(headless=False)

    click.echo(f"Looking up: {name!r}" + (f" near {location!r}" if location else ""))
    result = maps.lookup(name, location)
    if result is None:
        click.echo("No match found on Google Maps.", err=True)
        sys.exit(1)

    click.echo(f"  Location     : {result.general_location}")
    click.echo(f"  Name on Maps : {result.name_on_maps}")
    click.echo(f"  Exact addr   : {result.verified_location}")
    click.echo(f"  Phone        : {result.phone}")
    if result.website:
        click.echo(f"  Website      : {result.website}")

    if dry_run:
        click.echo("Dry run — not writing to Sheet.")
        return

    row_num = sheets.append_business(
        name=name,
        location=result.general_location,
        name_on_maps=result.name_on_maps,
        verified_location=result.verified_location,
        phone=result.phone,
    )
    click.echo(f"Wrote row {row_num}.")


@cli.command("enrich")
@click.option(
    "--delay",
    default=2.5,
    show_default=True,
    help="Seconds between Maps lookups (keep this polite)",
)
@click.option("--dry-run", is_flag=True, help="Print matches without writing")
@click.option("--limit", default=0, help="Max rows to process (0 = all)")
@click.option(
    "--fix-locations",
    is_flag=True,
    help="Also refresh Location for rows that only have the city (e.g. Tbilisi)",
)
@click.option(
    "--show-browser",
    is_flag=True,
    help="Show the browser window (useful if Maps blocks headless)",
)
def enrich_sheet(
    delay: float,
    dry_run: bool,
    limit: int,
    fix_locations: bool,
    show_browser: bool,
) -> None:
    """Fill Location / Name on Maps / Verified Location / Phone for incomplete rows."""
    maps, sheets, _settings = _clients()
    if show_browser:
        maps = MapsClient(headless=False)

    pending = sheets.rows_needing_enrichment(fix_locations=fix_locations)
    if limit > 0:
        pending = pending[:limit]

    if not pending:
        click.echo("Nothing to enrich.")
        return

    click.echo(f"Enriching {len(pending)} row(s)...")
    ok = skipped = failed = 0

    for item in pending:
        label = f"row {item['row']}: {item['name']}"

        # Already has Name on Maps; only fill blank phone cells.
        if (
            item.get("needs_phone_placeholder")
            and not item.get("needs_maps")
            and not item.get("needs_location")
        ):
            click.echo(f"  OK   {label} → phone = {NO_PHONE}")
            if not dry_run:
                sheets.update_phone_placeholder(item["row"])
            ok += 1
            continue

        try:
            result = maps.lookup(item["name"], item["location"] or "Tbilisi")
        except Exception as exc:  # noqa: BLE001 — surface errors per row
            click.echo(f"  FAIL {label} — {exc}", err=True)
            failed += 1
            time.sleep(delay)
            continue

        if result is None:
            click.echo(f"  SKIP {label} — no Maps match")
            skipped += 1
            time.sleep(delay)
            continue

        click.echo(
            f"  OK   {label} → {result.general_location} | "
            f"{result.name_on_maps} | {result.phone}"
        )
        if not dry_run:
            sheets.update_enrichment(
                item["row"],
                result.general_location,
                result.name_on_maps,
                result.verified_location,
                result.phone,
            )
        ok += 1
        time.sleep(delay)

    click.echo(f"Done. ok={ok} skipped={skipped} failed={failed}")


if __name__ == "__main__":
    cli()
