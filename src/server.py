"""Bare-bones FastMCP server for public health data.

Exposes a single ``health_check`` tool used to verify the server is reachable.
Future tickets add FDA RSS ingestion, public health news, and semantic search.

Run locally with::

    python -m src.server
"""

from fastmcp import FastMCP

mcp = FastMCP("public-health-mcp")


@mcp.tool()
def health_check() -> str:
    """Return ``"ok"`` to confirm the server is running.

    Used by clients to verify the connection is healthy before making
    real tool calls.
    """
    return "ok"


if __name__ == "__main__":
    mcp.run()
