# keboola-docs-mcp

A public, unauthenticated MCP server exposing a single tool — `docs_query` —
that answers natural-language questions about Keboola using the official docs
as the source of truth. It is a thin wrapper around the Keboola AI service's
`POST /docs/question` endpoint.

Designed to run as a **Keboola data app**. Any MCP client (Claude.ai custom
connectors, Claude Desktop, Cursor, etc.) can point at `/mcp` directly — there
is no bearer token, OAuth flow, or client-side credential of any kind.

```
client ──HTTPS, no auth──▶ Keboola data app ─▶ ai.keboola.com/docs/question
                                              (X-StorageAPI-Token held server-side)
```

## Tool

| Tool         | Args                   | Returns                                |
|--------------|------------------------|----------------------------------------|
| `docs_query` | `query: str`           | `{ text: str, source_urls: list[str] }` |

The shape matches the upstream `docs_query` in
[`keboola-mcp-server`](https://github.com/keboola/keboola-mcp-server) — clients
can swap one for the other with no observable behavior change.

## Configuration

Set these as Keboola data-app secrets (use the `#` prefix in the Console so
they are encrypted at rest):

| Env var                  | Required | Notes                                            |
|--------------------------|----------|--------------------------------------------------|
| `KBC_STORAGE_TOKEN`      | yes      | Keboola Storage API token used to call the AI service. Never leaves the server. |
| `KBC_AI_SERVICE_URL`     | no       | Defaults to `https://ai.keboola.com`.            |
| `PORT`                   | no       | Defaults to `5000` (matches Keboola convention). |

## Local development

```bash
cp .env.example .env
$EDITOR .env                    # set KBC_STORAGE_TOKEN
uv sync
uv run python server.py         # listens on :5000
```

Quick smoke test in a second terminal:

```bash
curl -s http://localhost:5000/healthz
# {"status":"ok","service":"keboola-docs-mcp"}
```

## Deploying as a Keboola data app

The repo layout matches the
[MCP-server-as-Keboola-data-app pattern](https://github.com/keboola-rnd/changelog-agent-ghost-mcp):

```
keboola-config/
├── setup.sh                                  # `uv sync` at container start
├── nginx/sites/default.conf                  # :8888 → :5000 proxy (SSE-safe)
└── supervisord/services/mcp-server.conf      # runs `uv run python server.py`
```

In the Keboola Console:

1. Create a new **Custom Python Data App** pointing at this repository.
2. Add the secret `#KBC_STORAGE_TOKEN` with your Storage API token value.
3. Deploy. Public URL will look like
   `docs-mcp-<id>.hub.<region>.<cloud>.keboola.com`.
4. Point any MCP client at `https://<that host>/mcp` — no auth header needed.

## How a client uses it

In Claude.ai custom connectors (or any MCP client supporting unauthenticated
servers), add a connector with:

- **Server URL**: `https://<your-host>/mcp`
- **Authentication**: none

The client will discover the `docs_query` tool automatically.

## Notes

- The MCP endpoint is intentionally open. The only credential involved is the
  server-side `KBC_STORAGE_TOKEN`, which is never returned to clients.
- Because the endpoint is public, expect anyone with the URL to be able to
  burn quota against your Storage API token. Use a dedicated, low-privilege
  token and rotate it if abuse occurs.
- The upstream `ai.keboola.com/docs/question` endpoint accepts any valid
  Storage API token regardless of project — the docs corpus is platform-wide.
