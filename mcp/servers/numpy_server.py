from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from mcp.services import numpy_svc

mcp = FastMCP("hospital-numpy")


@mcp.tool()
def feature_stats(columns: str = "") -> str:
    """NumPy stats on numeric gold feature columns (comma-separated or all)."""
    cols = [c.strip() for c in columns.split(",") if c.strip()] or None
    return str(numpy_svc.feature_array_stats(cols))


@mcp.tool()
def correlation(col_a: str, col_b: str) -> str:
    """Pearson correlation between two gold feature columns."""
    r = numpy_svc.correlation_pair(col_a, col_b)
    return str(r) if r is not None else "Unable to compute correlation."


if __name__ == "__main__":
    mcp.run()
