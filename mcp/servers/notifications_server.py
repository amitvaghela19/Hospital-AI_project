from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from mcp.services import chroma_svc, notifications_svc

mcp = FastMCP("hospital-notifications")


@mcp.tool()
def notify(title: str, message: str, level: str = "info") -> str:
    """Send a notification (log + optional Windows toast)."""
    return str(notifications_svc.notify(title, message, level))


@mcp.tool()
def list_notifications(limit: int = 20) -> str:
    """List recent MCP notifications."""
    return str(notifications_svc.list_notifications(limit))


@mcp.tool()
def rag_query(message: str) -> str:
    """Bonus: semantic RAG via Chroma (same as chroma server)."""
    result = chroma_svc.rag_query(message)
    return result or "No RAG hit."


if __name__ == "__main__":
    mcp.run()
