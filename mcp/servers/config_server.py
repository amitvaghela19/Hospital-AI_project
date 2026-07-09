from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from mcp.services import config_svc

mcp = FastMCP("hospital-config")


@mcp.tool()
def list_registry() -> str:
    """List all paths from datafile.txt registry."""
    return str(config_svc.load_datafile_registry())


@mcp.tool()
def get_rbac() -> str:
    """Return RBAC role permissions JSON."""
    return str(config_svc.get_rbac())


@mcp.tool()
def get_champion() -> str:
    """Return champion model register."""
    return str(config_svc.get_champion_register())


@mcp.tool()
def get_env() -> str:
    """Return environment variable summary for MCP services."""
    return str(config_svc.get_env_summary())


if __name__ == "__main__":
    mcp.run()
