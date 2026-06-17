"""FDA tool logic.

Plain async functions that take the shared ``FeedStore`` explicitly, so they're
unit-testable by passing a store directly. ``TOOL_FNS`` lists the ones exposed
as MCP tools; the generic :class:`~src.providers.SourceProvider` binds the store
and turns each into a tool, using the docstring as the client-facing description.
"""

from src.fda.ingestion import FDA_FEEDS, FeedStore, refresh_if_stale


async def _serve(store: FeedStore, source: str, limit: int) -> list[dict]:
    """Refresh ``source``'s feed if stale, then return up to ``limit`` items.

    Refresh is scoped to the one requested feed so a tool's latency and
    failure modes never depend on sibling feeds it doesn't read.
    (Cross-source tools refresh the union themselves; see src/cross_source_tools.py.)

    ``limit`` is clamped to ``>= 0`` so a negative value yields an empty list
    rather than silently dropping items off the end (e.g. ``[:-1]``).
    """
    if source not in FDA_FEEDS:
        raise ValueError(f"unknown FDA feed source: {source!r}")
    await refresh_if_stale(store, feeds={source: FDA_FEEDS[source]})
    items = store.get(source=source)[: max(0, limit)]
    return [item.model_dump(mode="json") for item in items]


async def get_recalls(store: FeedStore, limit: int = 20) -> list[dict]:
    """Latest FDA recalls and market withdrawals.

    Returns up to ``limit`` items, newest first. Cached ~15 minutes; may be
    empty on a cold start or while FDA is unreachable.
    """
    return await _serve(store, "fda_recalls", limit)


async def get_drug_updates(store: FeedStore, limit: int = 20) -> list[dict]:
    """Latest items from the FDA "What's New: Drugs" feed.

    A firehose of all drug-related FDA updates — guidances, workshops, AND
    approvals, not approvals only (the FDA publishes no approvals-only RSS
    feed). Filter on ``title`` for the update type you want. Returns up to
    ``limit`` items, newest first. Cached ~15 minutes.
    """
    return await _serve(store, "fda_drugs", limit)


async def get_safety_alerts(store: FeedStore, limit: int = 20) -> list[dict]:
    """Latest FDA MedWatch safety alerts (human medical products).

    Returns up to ``limit`` items, newest first. Cached ~15 minutes.
    """
    return await _serve(store, "fda_medwatch", limit)


# The source's tool functions, in the order they appear to clients. Each takes
# the shared store first; SourceProvider binds it and derives the tool name and
# description from each function. Add a tool by adding it here.
TOOL_FNS = [get_recalls, get_drug_updates, get_safety_alerts]
