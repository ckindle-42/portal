"""Runtime metrics for OpenAI-compatible endpoint."""

from __future__ import annotations

import os
import time

from prometheus_client import Counter, Gauge, Histogram

REQUESTS_PER_MINUTE = Gauge("portal_requests_per_minute", "Rolling requests per minute")
ACTIVE_USERS = Gauge("portal_active_users", "Unique users seen in process lifetime")
TOKENS_PER_SECOND = Histogram(
    "portal_tokens_per_second", "Tokens/sec during completion", buckets=(1, 5, 10, 20, 40, 80)
)
TTFT_MS = Histogram(
    "portal_ttft_ms", "Time to first token", buckets=(10, 50, 100, 250, 500, 1000, 2000, 5000)
)
MCP_TOOL_USAGE = Counter("portal_mcp_tool_usage_total", "MCP tool calls", ["tool_name"])
VRAM_MB = Gauge("portal_vram_usage_mb", "VRAM usage in MB")
UNIFIED_MEM_MB = Gauge("portal_unified_memory_usage_mb", "Unified memory usage in MB")

_start = time.time()
_seen_users: set[str] = set()
_requests = 0
_MAX_SEEN_USERS = 10_000


def mark_request(user_id: str) -> None:
    global _requests
    _requests += 1
    elapsed_min = max((time.time() - _start) / 60.0, 1 / 60)
    REQUESTS_PER_MINUTE.set(_requests / elapsed_min)
    if len(_seen_users) < _MAX_SEEN_USERS:
        _seen_users.add(user_id)
    ACTIVE_USERS.set(len(_seen_users))


def set_memory_stats() -> None:
    # Env-overridable so container orchestrators can push values.
    VRAM_MB.set(float(os.getenv("PORTAL_VRAM_USAGE_MB", "0")))
    UNIFIED_MEM_MB.set(float(os.getenv("PORTAL_UNIFIED_MEMORY_USAGE_MB", "0")))
