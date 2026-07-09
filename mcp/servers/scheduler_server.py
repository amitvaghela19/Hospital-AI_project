from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from mcp.services import scheduler_svc

mcp = FastMCP("hospital-scheduler")


@mcp.tool()
def register_job(name: str, command: str, cron_hint: str = "manual") -> str:
    """Register a schedulable job definition."""
    return str(scheduler_svc.register_job(name, command, cron_hint))


@mcp.tool()
def run_master_pipeline() -> str:
    """Execute master.ipynb end-to-end (long-running)."""
    return str(scheduler_svc.run_master_pipeline())


@mcp.tool()
def list_jobs() -> str:
    """List registered scheduler jobs."""
    return str(scheduler_svc.list_jobs())


if __name__ == "__main__":
    mcp.run()
