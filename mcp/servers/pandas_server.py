from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from mcp.services import pandas_svc

mcp = FastMCP("hospital-pandas")


@mcp.tool()
def semantic_metric(message: str) -> str:
    """Answer certified readmission/LOS metrics from mart_readmission."""
    result = pandas_svc.semantic_metric(message)
    return result or "No matching metric pattern."


@mcp.tool()
def describe_mart(name: str = "mart_readmission") -> str:
    """Pandas describe() on a certified export mart."""
    return pandas_svc.describe_mart(name)


@mcp.tool()
def groupby_metric(name: str, column: str, metric: str = "readmit_30d") -> str:
    """Group-by mean on a mart column."""
    return pandas_svc.groupby_metric(name, column, metric)


@mcp.tool()
def gold_features_sample(n: int = 5) -> str:
    """Preview rows from gold model_features.parquet."""
    return pandas_svc.load_gold_features_sample(n)


if __name__ == "__main__":
    mcp.run()
