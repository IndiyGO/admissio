from __future__ import annotations

import sys
from collections import Counter
from pathlib import Path

import httpx
import typer
from ldap3.core.exceptions import LDAPException
from pydantic import ValidationError
from rich.console import Console
from rich.table import Table

from . import __version__
from .config import Config, load_config
from .directories import DirectoryError, open_directory
from .engine import sync as run_sync
from .logins import LoginGenerator
from .models import Status
from .passwords import generate_password
from .report import write_report
from .rules import Rules
from .sources import load_new_hires

app = typer.Typer(
    add_completion=False,
    pretty_exceptions_enable=False,
    help="Provision directory accounts from HR new-hire data.",
)
console = Console()

STYLE = {
    Status.CREATED: "green",
    Status.WOULD_CREATE: "cyan",
    Status.EXISTS: "dim",
    Status.DUPLICATE: "yellow",
    Status.INVALID: "yellow",
    Status.FAILED: "red",
}

ConfigOpt = typer.Option(Path("config.yaml"), "--config", "-c", exists=True, dir_okay=False)


def _generator(cfg: Config) -> LoginGenerator:
    return LoginGenerator(
        cfg.login.patterns,
        max_suffix=cfg.login.max_suffix,
        max_length=cfg.login.max_length,
        particles=tuple(cfg.login.ignore_particles),
    )


@app.command()
def sync(
    config: Path = ConfigOpt,
    dry_run: bool = typer.Option(False, "--dry-run", help="Plan only; change nothing."),
    report: bool = typer.Option(True, help="Write a CSV report of the run."),
) -> None:
    """Read new hires and create the missing accounts."""
    cfg = load_config(config)
    hires = load_new_hires(cfg.source)
    console.print(f"[bold]{len(hires)}[/] record(s) from {cfg.source.type} source")

    directory = open_directory(cfg.directory)
    results = run_sync(
        hires,
        directory,
        Rules(cfg.rules),
        _generator(cfg),
        lambda: generate_password(cfg.password.length),
        dry_run=dry_run,
    )

    table = Table(title="Dry run - nothing was changed" if dry_run else "Sync results")
    for col in ("Status", "Employee", "Name", "Login", "Email", "OU", "Notes"):
        table.add_column(col, overflow="fold")
    for r in results:
        table.add_row(
            f"[{STYLE[r.status]}]{r.status.value}[/]",
            r.employee_id,
            r.full_name,
            r.login,
            r.email,
            r.ou,
            r.message,
        )
    console.print(table)

    counts = Counter(r.status.value for r in results)
    console.print(" | ".join(f"{k}: {v}" for k, v in sorted(counts.items())))

    if report and not dry_run:
        path = write_report(results, cfg.report.path, cfg.report.include_passwords)
        console.print(f"Report: [bold]{path}[/]")
        if cfg.report.include_passwords:
            console.print("[yellow]The report holds initial passwords - hand them over and delete it.[/]")

    if counts.get(Status.FAILED.value):
        raise typer.Exit(code=1)


@app.command()
def check(config: Path = ConfigOpt) -> None:
    """Validate the config, read the source and test the directory connection."""
    cfg = load_config(config)
    console.print("[green]OK[/] config is valid")
    console.print(f"[green]OK[/] source returned {len(load_new_hires(cfg.source))} record(s)")
    open_directory(cfg.directory)
    console.print(f"[green]OK[/] connected to {cfg.directory.type} directory")


@app.command()
def logins(
    name: str,
    config: Path = typer.Option(None, "--config", "-c", dir_okay=False),
) -> None:
    """Show which logins would be tried for a name, in order."""
    gen = (
        _generator(load_config(config))
        if config
        else LoginGenerator(["{first}.{last}", "{second}.{last}", "{first}.{last}{n}"])
    )
    for i, login in enumerate(gen.candidates(name), 1):
        console.print(f"{i:>2}. {login}")


@app.command()
def version() -> None:
    console.print(__version__)


def main() -> None:
    """Entry point: expected failures become one readable line instead of a traceback."""
    # Legacy Windows consoles (cp1252/cp850) can't print every name; degrade instead of crashing.
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(errors="replace")
    try:
        app()
    except ValidationError as exc:
        console.print(f"[red]Invalid config:[/] {exc}")
        raise SystemExit(2) from None
    except (DirectoryError, LDAPException, httpx.HTTPError, OSError, ValueError) as exc:
        console.print(f"[red]Error:[/] {exc}")
        raise SystemExit(2) from None


if __name__ == "__main__":
    main()
