from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from mcp.services import chroma_svc

mcp = FastMCP("hospital-chroma")


@mcp.tool()
def rag_query(message: str, n_results: int = 3) -> str:
    """Semantic RAG over project_knowledge Chroma collection."""
    result = chroma_svc.rag_query(message, n_results)
    return result or "No RAG results."


if __name__ == "__main__":
    mcp.run()
