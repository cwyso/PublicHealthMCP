"""Root FastMCP server for public health data.

A single FastMCP server with one shared :class:`FeedStore` owned here at the
composition root and injected into each source. The shared store is keyed by
source and aggregates across all of them, which is what lets cross-source tools
(see ``src/aggregate.py``) span every source.

Each source is a custom :class:`~fastmcp.server.providers.Provider` registered
under its own namespace, so it supplies its own tools and owns its own resource
lifecycle. Cross-source tools, which belong to no single source, are registered
directly on the server.

Run locally with ``python -m src.server``.
"""

from fastmcp import FastMCP

from src.aggregate import register as register_aggregate
from src.fda.ingestion import FeedStore
from src.fda.provider import FDAProvider


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
    # FDA is a custom Provider (owns its httpx client via lifespan); namespace
    # prefixes its tools to fda_*. Cross-source tools stay a plain registration.
    mcp.add_provider(FDAProvider(store), namespace="fda")
    register_aggregate(mcp, store)
    return mcp


mcp = build_server()


if __name__ == "__main__":
    mcp.run()
