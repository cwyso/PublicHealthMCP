"""FDA MCP tools.

Module-level async tool functions plus a ``register(mcp)`` hook that attaches
them under ``fda_``-prefixed names. Functions live at module scope (not inside
``register``) so they can be unit-tested directly.
"""

from fastmcp import FastMCP

from src.fda.ingestion import FeedStore, refresh_if_stale

# Module-level singleton, shared by the three tools. Single-process server,
# async event loop, no thread-safety concerns. Tests monkeypatch this module's
# ``_store`` and ``refresh_if_stale`` to control state without hitting the
# network.
_store = FeedStore()


async def _serve(source: str, limit: int) -> list[dict]:
    """Refresh if stale, then return up to ``limit`` items for ``source``.

    ``limit`` is clamped to ``>= 0`` so a negative value yields an empty list
    rather than silently dropping items off the end (e.g. ``[:-1]``).
    """
    await refresh_if_stale(_store)
    items = _store.get(source=source)[: max(0, limit)]
    return [item.model_dump(mode="json") for item in items]


async def get_recalls(limit: int = 20) -> list[dict]:
    """Latest FDA recalls and market withdrawals.

    Returns up to ``limit`` items, newest first. Cached ~15 minutes; may be
    empty on a cold start or while FDA is unreachable.
    """
    return await _serve("fda_recalls", limit)


async def get_drug_updates(limit: int = 20) -> list[dict]:
    """Latest items from the FDA "What's New: Drugs" feed.

    A firehose of all drug-related FDA updates — guidances, workshops, AND
    approvals, not approvals only (the FDA publishes no approvals-only RSS
    feed). Filter on ``title`` for the update type you want. Returns up to
    ``limit`` items, newest first. Cached ~15 minutes.
    """
    return await _serve("fda_drugs", limit)


async def get_safety_alerts(limit: int = 20) -> list[dict]:
    """Latest FDA MedWatch safety alerts (human medical products).

    Returns up to ``limit`` items, newest first. Cached ~15 minutes.
    """
    return await _serve("fda_medwatch", limit)


def register(mcp: FastMCP) -> None:
    """Attach the FDA tools to ``mcp`` with ``fda_``-prefixed names."""
    mcp.tool(get_recalls, name="fda_get_recalls")
    mcp.tool(get_drug_updates, name="fda_get_drug_updates")
    mcp.tool(get_safety_alerts, name="fda_get_safety_alerts")
