"""Root FastMCP server for public health data.

A single FastMCP server with one shared :class:`FeedStore` owned here at the
composition root and injected into each source. The shared store is keyed by
source and aggregates across all of them, which is what lets cross-source tools
(see ``src/cross_source_tools.py``) span every source.

Each source contributes a list of tool functions, exposed through the generic
:class:`~src.providers.SourceProvider` under the source's namespace. Adding a
source is one ``add_provider`` line. Cross-source tools, which belong to no
single source, are registered directly on the server.

Run locally with ``python -m src.server``.
"""

from fastmcp import FastMCP

from src.cross_source_tools import register as register_cross_source
from src.fda import tools as fda_tools
from src.fda.ingestion import FeedStore
from src.providers import SourceProvider


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
    # Each source = one SourceProvider under its namespace (prefixes tools to
    # e.g. fda_*). Cross-source tools stay a plain registration.
    mcp.add_provider(SourceProvider(fda_tools.TOOL_FNS, store), namespace="fda")
    register_cross_source(mcp, store)
    return mcp


mcp = build_server()


if __name__ == "__main__":
    mcp.run()
