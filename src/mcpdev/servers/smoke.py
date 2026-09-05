"""Smallest server that proves the toolchain works."""

from mcp.server.mcpserver import MCPServer

mcp = MCPServer("smoke-test")


@mcp.tool()
def ping_check(label: str = "hello") -> str:
    """Echo a label back, to prove the server answers."""
    return f"smoke test ok: {label}"


if __name__ == "__main__":
    mcp.run()
