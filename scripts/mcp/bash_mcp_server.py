"""Minimal bash MCP server with Redis-backed approval token."""

import os
import subprocess
import time
from typing import Any

import redis
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

app = FastAPI(title="portal-mcp-bash")
r = redis.from_url(os.getenv("REDIS_URL", "redis://localhost:6379/0"))


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
    completed = subprocess.run(req.command, shell=True, capture_output=True, text=True, timeout=20)
    return {"stdout": completed.stdout, "stderr": completed.stderr, "returncode": completed.returncode}


@app.post("/approve/{user_id}/{token}")
def approve(user_id: str, token: str) -> dict[str, Any]:
    r.setex(f"portal:approval:{user_id}:{token}", 60, "approved")
    return {"status": "approved", "expires_in": 60, "ts": time.time()}
