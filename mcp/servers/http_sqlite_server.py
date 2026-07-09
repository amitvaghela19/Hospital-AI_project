from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from mcp.services import http_svc, sqlite_svc

mcp = FastMCP("hospital-http-sqlite")


@mcp.tool()
def ollama_health() -> str:
    """Check Ollama availability and list models."""
    return str(http_svc.ollama_health())


@mcp.tool()
def ollama_generate(prompt: str, model: str = "") -> str:
    """Generate text via Ollama (non-clinical phrasing only)."""
    text, used = http_svc.ollama_generate(prompt, model or None)
    return text or f"Ollama failed for model={model or 'default'}"


@mcp.tool()
def sqlite_query(sql: str) -> str:
    """Run read-only SELECT against hospital.db warehouse."""
    return sqlite_svc.run_query(sql)


@mcp.tool()
def sqlite_tables() -> str:
    """List tables in SQLite warehouse."""
    return str(sqlite_svc.list_tables())


if __name__ == "__main__":
    mcp.run()
