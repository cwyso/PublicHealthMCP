"""Root FastMCP server for public health data.

A single FastMCP server with one shared :class:`FeedStore` owned here at the
composition root and injected into each source's ``register(mcp, store)``. The
shared store is keyed by source and aggregates across all of them, which is
what lets cross-source tools (see ``src/aggregate.py``) span every source.

To add a source: create its package with a ``register(mcp, store)`` hook and
call it in ``build_server`` below.

Run locally with ``python -m src.server``.
"""

from fastmcp import FastMCP

from src.aggregate import register as register_aggregate
from src.fda.ingestion import FeedStore
from src.fda.tools import register as register_fda


def health_check() -> str:
    """Return ``"ok"`` to confirm the server is running.

    Used by clients to verify the connection is healthy before making real
    tool calls.
    """
    return "ok"


def build_server(store: FeedStore | None = None) -> FastMCP:
    """Build the root server with all sources registered against one store.

    ``store`` is injectable so tests can pass a pre-populated store and get an
    isolated server; production uses a fresh shared store.
    """
    store = store if store is not None else FeedStore()
    mcp = FastMCP("public-health-mcp")
    mcp.tool(health_check)
    register_fda(mcp, store)
    register_aggregate(mcp, store)
    return mcp


mcp = build_server()


if __name__ == "__main__":
    mcp.run()
