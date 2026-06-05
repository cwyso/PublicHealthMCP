"""FDA MCP tools.

Core async functions take the shared ``FeedStore`` explicitly (injected at the
composition root, see ``src/server.py``) so they can be unit-tested by passing
a store directly. ``register(mcp, store)`` wraps them in client-facing tool
closures under ``fda_``-prefixed names; the closures carry the descriptions the
MCP client sees.
"""

from fastmcp import FastMCP

from src.fda.ingestion import FDA_FEEDS, FeedStore, refresh_if_stale


async def _serve(store: FeedStore, source: str, limit: int) -> list[dict]:
    """Refresh stale FDA feeds, then return up to ``limit`` items for ``source``.

    ``limit`` is clamped to ``>= 0`` so a negative value yields an empty list
    rather than silently dropping items off the end (e.g. ``[:-1]``).
    """
    await refresh_if_stale(store, feeds=FDA_FEEDS)
    items = store.get(source=source)[: max(0, limit)]
    return [item.model_dump(mode="json") for item in items]


async def get_recalls(store: FeedStore, limit: int = 20) -> list[dict]:
    """Core for ``fda_get_recalls``: recalls from ``store``, newest first."""
    return await _serve(store, "fda_recalls", limit)


async def get_drug_updates(store: FeedStore, limit: int = 20) -> list[dict]:
    """Core for ``fda_get_drug_updates``: drug-feed items, newest first."""
    return await _serve(store, "fda_drugs", limit)


async def get_safety_alerts(store: FeedStore, limit: int = 20) -> list[dict]:
    """Core for ``fda_get_safety_alerts``: MedWatch alerts, newest first."""
    return await _serve(store, "fda_medwatch", limit)


def register(mcp: FastMCP, store: FeedStore) -> None:
    """Attach the FDA tools to ``mcp``, bound to the shared ``store``."""

    @mcp.tool(name="fda_get_recalls")
    async def fda_get_recalls(limit: int = 20) -> list[dict]:
        """Latest FDA recalls and market withdrawals.

        Returns up to ``limit`` items, newest first. Cached ~15 minutes; may be
        empty on a cold start or while FDA is unreachable.
        """
        return await get_recalls(store, limit)

    @mcp.tool(name="fda_get_drug_updates")
    async def fda_get_drug_updates(limit: int = 20) -> list[dict]:
        """Latest items from the FDA "What's New: Drugs" feed.

        A firehose of all drug-related FDA updates — guidances, workshops, AND
        approvals, not approvals only (the FDA publishes no approvals-only RSS
        feed). Filter on ``title`` for the update type you want. Returns up to
        ``limit`` items, newest first. Cached ~15 minutes.
        """
        return await get_drug_updates(store, limit)

    @mcp.tool(name="fda_get_safety_alerts")
    async def fda_get_safety_alerts(limit: int = 20) -> list[dict]:
        """Latest FDA MedWatch safety alerts (human medical products).

        Returns up to ``limit`` items, newest first. Cached ~15 minutes.
        """
        return await get_safety_alerts(store, limit)
