"""Web search/scrape MCP server using scrapling + DDG fallback."""

from __future__ import annotations

from fastapi import FastAPI
from pydantic import BaseModel
import httpx

app = FastAPI(title="portal-mcp-web")


class SearchRequest(BaseModel):
    query: str


@app.post("/tool/search")
async def search(req: SearchRequest) -> dict:
    # lightweight DDG instant-answer fallback
    url = "https://api.duckduckgo.com/"
    params = {"q": req.query, "format": "json", "no_redirect": 1, "no_html": 1}
    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.get(url, params=params)
        data = resp.json()
    abstract = data.get("AbstractText") or "No instant answer."
    return {"markdown": f"## Search Result\n\n**Query:** {req.query}\n\n{abstract}"}
