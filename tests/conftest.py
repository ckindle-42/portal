"""
Pytest configuration for all Portal tests — validates the environment,
registers markers, and applies xfail markers to known-failing legacy API tests.
"""

import sys

import pytest


def pytest_configure(config):
    """Validate test environment and configure pytest with custom markers."""
    missing = []
    for mod in ("httpx", "aiohttp", "fastapi", "pydantic"):
        try:
            __import__(mod)
        except ImportError:
            missing.append(mod)

    if missing:
        print(
            "\n"
            "=" * 70 + "\n"
            " TEST ENVIRONMENT ERROR\n"
            "=" * 70 + "\n"
            f"\n"
            f" Missing dependencies: {', '.join(missing)}\n"
            f"\n"
            f" Portal must be installed before running tests.\n"
            f" Run one of:\n"
            f"\n"
            f"   pip install -e '.[dev]'     # pip (includes all extras)\n"
            f"   uv sync --all-extras --dev  # uv\n"
            f"   make install                # Makefile shortcut\n"
            f"\n"
            "=" * 70,
            file=sys.stderr,
        )
        raise SystemExit(1)

    try:
        import portal  # noqa: F401
    except ImportError:
        print(
            "\n"
            "=" * 70 + "\n"
            " Portal package not installed.\n"
            " Run: pip install -e '.[dev]'\n"
            "=" * 70,
            file=sys.stderr,
        )
        raise SystemExit(1)

    config.addinivalue_line(
        "markers", "unit: Fast unit tests with no external dependencies"
    )
    config.addinivalue_line(
        "markers", "integration: Integration tests requiring external services"
    )
    config.addinivalue_line(
        "markers", "e2e: End-to-end tests for full workflows"
    )
    config.addinivalue_line(
        "markers", "slow: Tests that take more than 5 seconds"
    )
    config.addinivalue_line(
        "markers", "requires_docker: Tests requiring Docker"
    )
    config.addinivalue_line(
        "markers", "requires_llm: Tests requiring LLM backend"
    )
