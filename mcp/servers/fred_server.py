from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from mcp.services import fred_svc

mcp = FastMCP("hospital-fred")


@mcp.tool()
def fetch_series(series_id: str, limit: int = 12) -> str:
    """Fetch FRED macro series (analyst context only, not clinical input)."""
    return str(fred_svc.fetch_series(series_id, limit))


@mcp.tool()
def list_series() -> str:
    """List default FRED series IDs available for analyst chat."""
    return str(fred_svc.list_default_series())


if __name__ == "__main__":
    mcp.run()
