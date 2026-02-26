"""Minimal bash MCP server with Redis-backed approval token."""

import os
import shlex
import subprocess
import time
from typing import Any

import redis
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

app = FastAPI(title="portal-mcp-bash")
r = redis.from_url(os.getenv("REDIS_URL", "redis://localhost:6379/0"))

_ALLOWED_BINARIES = frozenset({
    "ls", "cat", "head", "tail", "wc", "grep", "find", "echo", "date",
    "pwd", "whoami", "uname", "df", "du", "free", "uptime", "env", "printenv",
})
_MAX_CMD_LENGTH = 2000
_MAX_ARGS = 50


class BashRequest(BaseModel):
    user_id: str
    command: str
    approval_token: str


@app.post("/tool/bash")
def execute(req: BashRequest) -> dict[str, Any]:
    key = f"portal:approval:{req.user_id}:{req.approval_token}"
    value = r.get(key)
    if value != b"approved":
        raise HTTPException(status_code=403, detail="Command not approved")
    r.delete(key)

    if len(req.command) > _MAX_CMD_LENGTH:
        raise HTTPException(status_code=400, detail="Command exceeds maximum length")

    try:
        args = shlex.split(req.command)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=f"Malformed command: {exc}")

    if not args:
        raise HTTPException(status_code=400, detail="Empty command")
    if len(args) > _MAX_ARGS:
        raise HTTPException(status_code=400, detail="Too many arguments")
    if args[0] not in _ALLOWED_BINARIES:
        raise HTTPException(status_code=403, detail=f"Binary not allowed: {args[0]}")

    completed = subprocess.run(args, capture_output=True, text=True, timeout=20)
    return {"stdout": completed.stdout, "stderr": completed.stderr, "returncode": completed.returncode}


@app.post("/approve/{user_id}/{token}")
def approve(user_id: str, token: str) -> dict[str, Any]:
    r.setex(f"portal:approval:{user_id}:{token}", 60, "approved")
    return {"status": "approved", "expires_in": 60, "ts": time.time()}
