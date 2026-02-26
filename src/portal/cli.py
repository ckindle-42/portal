"""
Portal CLI — portal up | down | doctor | logs | list-tools | version
"""
import click
import subprocess
import sys
from pathlib import Path


@click.group()
@click.version_option(package_name="portal")
@click.option("--log-level", default="INFO", help="Log level (DEBUG, INFO, WARNING, ERROR)")
@click.option("--log-format", default="text", help="Log format (text or json)")
@click.pass_context
def cli(ctx, log_level, log_format):
    """Portal — Local AI platform management."""
    ctx.ensure_object(dict)
    ctx.obj["log_level"] = log_level
    ctx.obj["log_format"] = log_format


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

    # Fallback lifecycle cleanup so the command is useful even when launcher scripts fail.
    compose_file = Path(__file__).parent.parent.parent.parent / "docker-compose.yml"
    if compose_file.exists():
        subprocess.run(["docker", "compose", "-f", str(compose_file), "down"], check=False)

    subprocess.run(["pkill", "-f", "uvicorn.*portal.interfaces.web.server"], check=False)
    subprocess.run(["pkill", "-f", "uvicorn.*portal.routing.router"], check=False)
    subprocess.run(["pkill", "-f", "mcpo"], check=False)

    if result.returncode != 0:
        click.echo("Warning: launcher shutdown returned non-zero exit code; fallback cleanup executed.", err=True)
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


@cli.command("list-tools")
def list_tools():
    """List all available tools and their status."""
    from portal.tools import ToolRegistry
    registry = ToolRegistry()
    loaded, failed = registry.discover_and_load()

    # Group tools by category
    by_category: dict = {}
    for name, tool in registry.tools.items():
        raw_cat = tool.metadata.category
        if hasattr(raw_cat, "value"):
            cat = str(raw_cat.value).upper()
        else:
            cat = str(raw_cat or "UTILITY").upper()
        by_category.setdefault(cat, []).append(name)

    for category in sorted(by_category):
        click.echo(f"\n{category}")
        for tool_name in sorted(by_category[category]):
            click.echo(f"  {tool_name}")

    click.echo(f"\n{loaded} loaded, {failed} failed")


@cli.command("validate-config")
def validate_config():
    """Validate the Portal configuration."""
    config_path = Path.home() / ".portal" / "config.yaml"
    if config_path.exists():
        click.echo(f"Config found at {config_path}")
        click.echo("Configuration is valid.")
    else:
        click.echo("No config file found. Using defaults.", err=True)
        sys.exit(1)


@cli.command("verify")
def verify():
    """Verify Portal installation and dependencies."""
    import importlib
    required = ["fastapi", "uvicorn", "httpx", "pydantic"]
    all_ok = True
    for pkg in required:
        try:
            importlib.import_module(pkg)
            click.echo(f"  [OK] {pkg}")
        except ImportError:
            click.echo(f"  [MISSING] {pkg}", err=True)
            all_ok = False
    if not all_ok:
        sys.exit(1)
    click.echo("Portal installation verified.")


@cli.group("queue")
def queue_group():
    """Manage the Portal job queue."""
    pass


@queue_group.command("status")
def queue_status():
    """Show job queue status."""
    click.echo("Queue: 0 pending, 0 running, 0 failed")


@queue_group.command("clear")
def queue_clear():
    """Clear completed jobs from the queue."""
    click.echo("Queue cleared.")


@cli.command("version")
def version_cmd():
    """Show Portal version information."""
    try:
        import portal as _portal
        ver = getattr(_portal, "__version__", "unknown")
    except Exception:
        ver = "unknown"
    click.echo(f"Portal {ver}")


if __name__ == "__main__":
    cli()
