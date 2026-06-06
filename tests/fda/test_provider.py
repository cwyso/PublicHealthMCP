"""Tests for src.fda.provider.FDAProvider.

Covers the provider's lifecycle (lifespan opens/closes the shared client),
that the framework actually runs that lifespan for an in-memory client session,
the tool inventory it supplies, and end-to-end reachability under the namespace.
"""

from datetime import datetime, timezone
from unittest.mock import AsyncMock

import httpx
import pytest
from fastmcp import Client, FastMCP

from src.fda import tools as fda_tools
from src.fda.ingestion import FeedItem, FeedStore
from src.fda.provider import FDAProvider


def _seed_recall(store: FeedStore, title: str) -> None:
    store.update(
        "fda_recalls",
        [
            FeedItem(
                id="p1",
                source="fda_recalls",
                title=title,
                summary="...",
                url="https://example.com/p1",
                published_at=datetime.now(timezone.utc),
                raw={},
            )
        ],
    )


async def test_lifespan_opens_and_closes_client():
    """lifespan() owns one httpx client: created on enter, closed on exit."""
    provider = FDAProvider(FeedStore())
    assert provider._client is None

    async with provider.lifespan():
        assert isinstance(provider._client, httpx.AsyncClient)
        assert not provider._client.is_closed

    assert provider._client is None


async def test_list_tools_exposes_bare_names():
    """The provider supplies bare-named tools; the fda_ prefix comes from the
    namespace at registration time, not from the tool names themselves."""
    provider = FDAProvider(FeedStore())
    tools = await provider._list_tools()
    names = {t.name for t in tools}
    assert names == {"get_recalls", "get_drug_updates", "get_safety_alerts"}


async def test_lifespan_runs_under_in_memory_client():
    """The framework runs the provider lifespan for an in-memory Client session:
    the client is opened on connect and closed on disconnect."""
    provider = FDAProvider(FeedStore())
    mcp = FastMCP("t")
    mcp.add_provider(provider, namespace="fda")

    assert provider._client is None
    async with Client(mcp):
        assert provider._client is not None
        assert not provider._client.is_closed
    assert provider._client is None


async def test_namespaced_tool_callable(monkeypatch):
    """End-to-end: fda_get_recalls (provider tool + fda_ namespace) returns
    seeded data through the in-memory client."""
    monkeypatch.setattr(fda_tools, "refresh_if_stale", AsyncMock(return_value=None))
    store = FeedStore()
    _seed_recall(store, "Prov recall")

    mcp = FastMCP("t")
    mcp.add_provider(FDAProvider(store), namespace="fda")

    async with Client(mcp) as client:
        result = await client.call_tool("fda_get_recalls", {"limit": 5})

    text = " ".join(b.text for b in result.content if hasattr(b, "text"))
    assert "Prov recall" in text


async def test_tool_propagates_refresh_error(monkeypatch):
    """The provider does not swallow unexpected refresh errors — they surface to
    the caller (with the lifespan client active)."""

    async def boom(*args, **kwargs):
        raise httpx.TimeoutException("simulated refresh failure")

    monkeypatch.setattr(fda_tools, "refresh_if_stale", boom)
    provider = FDAProvider(FeedStore())

    async with provider.lifespan():
        with pytest.raises(httpx.TimeoutException):
            await provider._get_recalls(5)
