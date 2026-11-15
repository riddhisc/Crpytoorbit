"""Terminal client for the same services the API uses.

Examples:
  orbit import sample-data/wazirx_trades.csv
  orbit reconcile
  orbit exceptions --status open --severity high
  orbit export --format csv
"""

from pathlib import Path

import typer
from sqlmodel import col, select

from app.db import run_migrations, session_scope
from app.models import ExceptionRecord, Job
from app.reconcile.service import reconcile
from app.services.export import exceptions_csv, ledger_csv
from app.services.ingest import ingest_files, preflight

cli = typer.Typer(no_args_is_help=True, help="Crypto Orbit reconciliation commands.")


def _ready() -> None:
    run_migrations()


@cli.command("import")
def import_files(files: list[Path]) -> None:
    """Normalize one or more CSV or JSON exports and reconcile."""
    _ready()
    payloads = [(path.name, path.read_bytes()) for path in files]
    with session_scope() as session:
        preflight(payloads, session)
        job = Job(kind="cli-import", status="queued")
        session.add(job)
        session.commit()
        session.refresh(job)
        result = ingest_files(session, job, payloads)
    imported_files = result["files"]
    summary = result["reconcile"]
    file_count = len(imported_files) if isinstance(imported_files, list) else 0
    open_count = summary.get("open_exceptions", 0) if isinstance(summary, dict) else 0
    typer.echo(f"Imported {file_count} file(s). Open exceptions: {open_count}")


@cli.command("reconcile")
def reconcile_cmd() -> None:
    """Re-run matching and exception rules. Resolved items stay resolved."""
    _ready()
    with session_scope() as session:
        summary = reconcile(session)
    typer.echo(f"Matches: {summary['matches']}. Open exceptions: {summary['open_exceptions']}")


@cli.command()
def export(format: str = typer.Option("csv", "--format")) -> None:
    """Write the ledger or exceptions to stdout."""
    _ready()
    with session_scope() as session:
        if format == "exceptions":
            typer.echo(exceptions_csv(session), nl=False)
        else:
            typer.echo(ledger_csv(session), nl=False)


@cli.command()
def exceptions(
    status: str = typer.Option("open", "--status"),
    severity: str | None = typer.Option(None, "--severity"),
) -> None:
    """List exceptions for a cron job or a support call."""
    _ready()
    with session_scope() as session:
        query = select(ExceptionRecord).where(ExceptionRecord.status == status)
        if severity:
            query = query.where(ExceptionRecord.severity == severity)
        rows = session.exec(query.order_by(col(ExceptionRecord.estimated_value_inr).desc())).all()
    if not rows:
        typer.echo("No exceptions.")
        return
    for row in rows:
        asset = row.asset or "-"
        typer.echo(f"{row.severity:6} {row.type:28} {asset:6} {row.explanation}")


def main() -> None:
    cli()


if __name__ == "__main__":
    main()
