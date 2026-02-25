"""
Portal CLI — portal up | down | doctor | logs
"""
import click
import subprocess
import sys
from pathlib import Path


@click.group()
@click.version_option(package_name="portal")
def cli():
    """Portal — Local AI platform management."""
    pass


@cli.command()
@click.option("--minimal", is_flag=True, help="Router + Ollama only (no Docker)")
def up(minimal: bool):
    """Start the Portal stack."""
    hardware_dir = Path(__file__).parent.parent.parent.parent / "hardware"
    # Detect platform and run appropriate launcher
    if sys.platform == "darwin":
        launcher = hardware_dir / "m4-mac" / "launch.sh"
    else:
        launcher = hardware_dir / "linux-bare" / "launch.sh"

    args = [str(launcher)]
    if minimal:
        args.append("--minimal")

    click.echo(f"Starting Portal ({launcher.name})...")
    subprocess.run(args, check=True)


@cli.command()
def down():
    """Stop the Portal stack."""
    hardware_dir = Path(__file__).parent.parent.parent.parent / "hardware"
    if sys.platform == "darwin":
        launcher = hardware_dir / "m4-mac" / "launch.sh"
    else:
        launcher = hardware_dir / "linux-bare" / "launch.sh"

    click.echo("Stopping Portal stack...")
    result = subprocess.run([str(launcher), "down"], check=False)
    if result.returncode != 0:
        click.echo("Warning: shutdown script returned non-zero exit code", err=True)
        sys.exit(result.returncode)


@cli.command()
def doctor():
    """Health check all Portal components."""
    import asyncio
    from portal.observability.health import run_health_check
    asyncio.run(run_health_check())


@cli.command()
@click.argument("service", required=False)
def logs(service: str | None):
    """Tail Portal logs. Optional: specify service name."""
    log_dir = Path.home() / ".portal" / "logs"
    if service:
        log_file = log_dir / f"{service}.log"
    else:
        log_file = log_dir / "portal.log"

    if not log_file.exists():
        click.echo(f"No log file found at {log_file}")
        return

    subprocess.run(["tail", "-f", str(log_file)])


if __name__ == "__main__":
    cli()
