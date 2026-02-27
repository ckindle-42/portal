"""Shared helpers for docker tools — avoids per-file try/except import boilerplate."""
from __future__ import annotations

try:
    import docker
    import docker.errors

    DOCKER_AVAILABLE = True
except ImportError:
    DOCKER_AVAILABLE = False
    docker = None  # type: ignore[assignment]

__all__ = ["DOCKER_AVAILABLE", "docker"]
