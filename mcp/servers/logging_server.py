from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from mcp.services import logging_svc

mcp = FastMCP("hospital-logging")


@mcp.tool()
def append_audit(role: str, action: str) -> str:
    """Append an audit event for RBAC-tracked actions."""
    entry = logging_svc.append_audit(role, action)
    return str(entry)


@mcp.tool()
def read_audit(limit: int = 20) -> str:
    """Read recent audit events."""
    return str(logging_svc.read_audit(limit))


@mcp.tool()
def append_pipeline_run(run_id: str, phase: str, status: str, detail: str = "") -> str:
    """Log a pipeline phase run for lineage."""
    return str(logging_svc.append_pipeline_run(run_id, phase, status, detail))


if __name__ == "__main__":
    mcp.run()
