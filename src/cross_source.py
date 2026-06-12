"""Cross-source MCP tools.

Tools here span multiple sources, so they belong to no single source package.
They read the shared ``FeedStore`` (which is keyed by source and aggregates
across all of them) and refresh the union of every source's feeds.

``ALL_FEEDS`` is that union — one spread per source. When a new source is
added, add its feed map here.
"""

from fastmcp import FastMCP

from src.fda.ingestion import FDA_FEEDS, FeedStore, refresh_if_stale

# Union of every source's {source_key: url} map. Extend per source, e.g.
# ALL_FEEDS = {**FDA_FEEDS, **CDC_FEEDS}.
ALL_FEEDS: dict[str, str] = {**FDA_FEEDS}


async def recent(
    store: FeedStore,
    sources: list[str] | None = None,
    limit: int = 20,
) -> list[dict]:
    """Most recent items across sources, merged newest-first.

    ``sources`` filters to those source keys (e.g. ``["fda_recalls"]``); ``None``
    spans every source. ``limit`` is clamped to ``>= 0``.
    """
    # Invariant: ALL_FEEDS must list every source whose items store.get(None)
    # can return. A source present in the store but missing from ALL_FEEDS is
    # never refreshed by this path and would be served perpetually stale.
    await refresh_if_stale(store, feeds=ALL_FEEDS)
    items = store.get(source=None)  # already newest-first across all sources
    if sources:
        wanted = set(sources)
        items = [i for i in items if i.source in wanted]
    items = items[: max(0, limit)]
    return [item.model_dump(mode="json") for item in items]


def register(mcp: FastMCP, store: FeedStore) -> None:
    """Attach cross-source tools to ``mcp``, bound to the shared ``store``."""

    @mcp.tool(name="get_recent")
    async def get_recent(
        sources: list[str] | None = None, limit: int = 20
    ) -> list[dict]:
        """Most recent public-health items across sources, merged newest-first.

        Unlike the source-specific tools (e.g. ``fda_get_recalls``), this merges
        items from every feed and sorts by recency, so it answers "what's the
        latest across everything" rather than "what's the latest of one
        category." Pass ``sources`` (source keys like ``"fda_recalls"``,
        ``"fda_drugs"``) to restrict the span; omit it for all sources. Returns
        up to ``limit`` items. Cached ~15 minutes.
        """
        return await recent(store, sources, limit)
