# Hospital MCP Servers

Custom [Model Context Protocol](https://modelcontextprotocol.io/) servers for the Healthcare Patient Readmission project.

## Layers

| Layer | Config | Consumer |
|-------|--------|----------|
| **IDE** | [`.cursor/mcp.json`](../.cursor/mcp.json) | Cursor agent during development |
| **Runtime** | [`mcp/client/pool.py`](client/pool.py) | `app_streamlit.py`, Phase 5 LangGraph router |

## Run a server locally

From project root with venv activated:

```powershell
$env:PYTHONPATH = (Get-Location).Path
python -m mcp.servers.logging_server
python -m mcp.servers.pandas_server
python -m mcp.servers.chroma_server
```

## Infrastructure

```powershell
docker compose -f docker-compose.mcp.yml up -d
python scripts/mcp_healthcheck.py
```

## Full documentation

See [`docs/mcp.md`](../docs/mcp.md).
