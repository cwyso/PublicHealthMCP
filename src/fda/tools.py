"""FDA tool logic.

Plain async functions that take the shared ``FeedStore`` (and optionally a
caller-owned httpx client) explicitly, so they're unit-testable without a
running server or provider lifespan. ``FDAProvider`` (src/fda/provider.py)
supplies these to the server; their docstrings become the MCP tool descriptions
the client sees.
"""

import httpx

from src.fda.ingestion import FDA_FEEDS, FeedStore, refresh_if_stale


async def _serve(
    store: FeedStore,
    source: str,
    limit: int,
    client: httpx.AsyncClient | None,
) -> list[dict]:
    """Refresh stale FDA feeds, then return up to ``limit`` items for ``source``.

    ``limit`` is clamped to ``>= 0`` so a negative value yields an empty list
    rather than silently dropping items off the end (e.g. ``[:-1]``).
    """
    await refresh_if_stale(store, feeds=FDA_FEEDS, client=client)
    items = store.get(source=source)[: max(0, limit)]
    return [item.model_dump(mode="json") for item in items]


async def get_recalls(
    store: FeedStore, limit: int = 20, *, client: httpx.AsyncClient | None = None
) -> list[dict]:
    """Latest FDA recalls and market withdrawals.

    Returns up to ``limit`` items, newest first. Cached ~15 minutes; may be
    empty on a cold start or while FDA is unreachable.
    """
    return await _serve(store, "fda_recalls", limit, client)


async def get_drug_updates(
    store: FeedStore, limit: int = 20, *, client: httpx.AsyncClient | None = None
) -> list[dict]:
    """Latest items from the FDA "What's New: Drugs" feed.

    A firehose of all drug-related FDA updates — guidances, workshops, AND
    approvals, not approvals only (the FDA publishes no approvals-only RSS
    feed). Filter on ``title`` for the update type you want. Returns up to
    ``limit`` items, newest first. Cached ~15 minutes.
    """
    return await _serve(store, "fda_drugs", limit, client)


async def get_safety_alerts(
    store: FeedStore, limit: int = 20, *, client: httpx.AsyncClient | None = None
) -> list[dict]:
    """Latest FDA MedWatch safety alerts (human medical products).

    Returns up to ``limit`` items, newest first. Cached ~15 minutes.
    """
    return await _serve(store, "fda_medwatch", limit, client)
