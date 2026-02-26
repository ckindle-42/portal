"""Allow `python -m portal` to invoke the CLI."""
from portal.cli import cli

if __name__ == "__main__":
    cli()
