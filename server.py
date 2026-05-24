"""docs-mcp — public, unauthenticated MCP server exposing a single docs_query
tool backed by Keboola's AI service (ai.keboola.com/docs/question).

The MCP /mcp endpoint accepts unauthenticated requests by design. The
server-side Keboola Storage API token is held as an env var and is never
exposed to clients — it is used only to authenticate the upstream call to
the Keboola AI service.

Deployment: runs as a Keboola data app. Nginx fronts on 8888 and proxies
/mcp to this process on $PORT. See keboola-config/ for the supporting
config files.

Required env vars:
    KBC_STORAGE_TOKEN     Keboola Storage API token. Held server-side.
                          On a Keboola data app, add as a `#`-prefixed secret.

Optional env vars:
    KBC_AI_SERVICE_URL    Defaults to https://ai.us-east4.gcp.keboola.com.
    PORT                  Defaults to 5000 (Keboola data app convention).
"""

from __future__ import annotations

import logging
import os
from typing import Annotated

import httpx
from mcp.server.fastmcp import FastMCP
from pydantic import BaseModel, Field
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
log = logging.getLogger("docs-mcp")

KBC_STORAGE_TOKEN = os.environ["KBC_STORAGE_TOKEN"]
KBC_AI_SERVICE_URL = os.environ.get("KBC_AI_SERVICE_URL", "https://ai.us-east4.gcp.keboola.com").rstrip("/")

mcp = FastMCP("keboola-docs-mcp")


class DocsAnswer(BaseModel):
    """An answer to a documentation query."""

    text: str = Field(description="Text of the answer to a documentation query.")
    source_urls: list[str] = Field(
        default_factory=list,
        description="List of URLs to the sources of the answer.",
    )


@mcp.tool()
async def docs_query(
    query: Annotated[
        str,
        Field(description="Natural language query to search for in the Keboola documentation."),
    ],
) -> DocsAnswer:
    """Answer a question using the Keboola documentation as a source."""
    async with httpx.AsyncClient(timeout=60.0) as client:
        resp = await client.post(
            f"{KBC_AI_SERVICE_URL}/docs/question",
            headers={
                "X-StorageAPI-Token": KBC_STORAGE_TOKEN,
                "Accept": "application/json",
            },
            json={"query": query},
        )

    if resp.status_code >= 400:
        log.warning("docs/question failed status=%s body=%s", resp.status_code, resp.text[:500])
        raise RuntimeError(f"Keboola AI service returned {resp.status_code}: {resp.text[:500]}")

    body = resp.json()
    return DocsAnswer(text=body["text"], source_urls=body.get("sourceUrls", []))


async def _healthz(_: Request) -> JSONResponse:
    return JSONResponse({"status": "ok", "service": "keboola-docs-mcp"})


app = mcp.streamable_http_app()
app.routes.append(Route("/healthz", _healthz, methods=["GET"]))


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        app,
        host="0.0.0.0",
        port=int(os.environ.get("PORT", "5000")),
        log_level="info",
    )
