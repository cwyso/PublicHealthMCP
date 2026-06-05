"""Root FastMCP server for public health data.

A single FastMCP server. Each source lives in its own package and exposes a
``register(mcp)`` hook that attaches its tools under a source prefix (``fda_``,
``cdc_``, ...) so names never collide. To add a source, create the package and
call its ``register`` below.

Run locally with ``python -m src.server``.
"""

from fastmcp import FastMCP

from src.fda.tools import register as register_fda

mcp = FastMCP("public-health-mcp")


@mcp.tool()
def health_check() -> str:
    """Return ``"ok"`` to confirm the server is running.

    Used by clients to verify the connection is healthy before making real
    tool calls.
    """
    return "ok"


register_fda(mcp)


if __name__ == "__main__":
    mcp.run()
