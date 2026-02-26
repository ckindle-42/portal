"""
Portal CLI — portal up | down | doctor | logs
"""
import socket
import subprocess
import sys
from pathlib import Path

import click


def _check_ports_available(ports: list[tuple[int, str]]) -> list[str]:
    """Check if required ports are free. Returns list of error messages."""
    errors = []
    for port, service in ports:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(0.5)
            if s.connect_ex(("127.0.0.1", port)) == 0:
                errors.append(
                    f"  Port {port} ({service}) is already in use. "
                    f"Stop the conflicting process or set {service.upper().replace('-', '_')}_PORT in .env"
                )
    return errors


@click.group()
@click.version_option(package_name="portal")
def cli() -> None:
    """Portal — Local AI platform management."""
    pass


@cli.command()
@click.option("--minimal", is_flag=True, help="Router + Ollama only (no Docker)")
@click.option("--skip-port-check", is_flag=True, help="Skip port availability check")
@click.option(
    "--profile",
    type=click.Choice(["m4-mac", "linux-bare", "linux-wsl2"]),
    default=None,
    help="Hardware profile (auto-detected if omitted)",
)
def up(minimal: bool, skip_port_check: bool, profile: str | None) -> None:
    """Start the Portal stack."""
    if not skip_port_check:
        required_ports = [
            (8081, "portal-api"),
            (8080, "web-ui"),
            (11434, "ollama"),
        ]
        if not minimal:
            required_ports.extend([
                (6379, "redis"),
                (6333, "qdrant"),
            ])
        errors = _check_ports_available(required_ports)
        if errors:
            click.echo("Port conflict detected:\n" + "\n".join(errors), err=True)
            click.echo("\nUse --skip-port-check to bypass.", err=True)
            raise SystemExit(1)

    repo_root = Path(__file__).parent.parent.parent.parent
    unified = repo_root / "launch.sh"

    if unified.exists():
        args = ["bash", str(unified), "up"]
        if minimal:
            args.append("--minimal")
        if profile:
            args.extend(["--profile", profile])
        click.echo("Starting Portal...")
        subprocess.run(args, check=True)
    else:
        # Legacy fallback to per-platform scripts
        hardware_dir = repo_root / "hardware"
        if sys.platform == "darwin":
            launcher = hardware_dir / "m4-mac" / "launch.sh"
        else:
            launcher = hardware_dir / "linux-bare" / "launch.sh"
        args = ["bash", str(launcher), "up"]
        if minimal:
            args.append("--minimal")
        click.echo(f"Starting Portal ({launcher.name})...")
        subprocess.run(args, check=True)


@cli.command()
def down() -> None:
    """Stop the Portal stack."""
    repo_root = Path(__file__).parent.parent.parent.parent
    unified = repo_root / "launch.sh"

    click.echo("Stopping Portal stack...")
    if unified.exists():
        result = subprocess.run(["bash", str(unified), "down"], check=False)
    else:
        # Legacy fallback to per-platform scripts
        hardware_dir = repo_root / "hardware"
        if sys.platform == "darwin":
            launcher = hardware_dir / "m4-mac" / "launch.sh"
        else:
            launcher = hardware_dir / "linux-bare" / "launch.sh"
        result = subprocess.run(["bash", str(launcher), "down"], check=False)

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
def doctor() -> None:
    """Health check all Portal components."""
    import asyncio

    from portal.observability.health import run_health_check
    asyncio.run(run_health_check())


@cli.command()
@click.argument("service", required=False)
def logs(service: str | None) -> None:
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
