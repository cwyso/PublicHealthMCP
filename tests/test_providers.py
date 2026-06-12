"""Tests for src.providers.SourceProvider.

The generic provider derives tool names from function ``__name__``, descriptions
from docstrings, binds the shared store out of the schema, and works for any
tool signature — the last point is what makes it source-agnostic.
"""

from datetime import datetime, timezone
from unittest.mock import AsyncMock

import pytest
from fastmcp import Client, FastMCP

from src.fda import tools as fda_tools
from src.fda.ingestion import FeedItem, FeedStore
from src.providers import SourceProvider


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


async def test_tool_names_come_from_function_names():
    """Tool names are derived from __name__, not hardcoded."""
    provider = SourceProvider(fda_tools.TOOL_FNS, FeedStore())
    names = {t.name for t in await provider._list_tools()}
    assert names == {"get_recalls", "get_drug_updates", "get_safety_alerts"}


async def test_descriptions_preserved_from_docstrings():
    """The description shipped to clients is the function's docstring."""
    provider = SourceProvider(fda_tools.TOOL_FNS, FeedStore())
    by_name = {t.name: t for t in await provider._list_tools()}
    assert by_name["get_recalls"].description == fda_tools.get_recalls.__doc__


async def test_store_is_bound_out_of_the_schema():
    """The bound store is not a client-facing parameter; the rest remain."""
    provider = SourceProvider(fda_tools.TOOL_FNS, FeedStore())
    by_name = {t.name: t for t in await provider._list_tools()}
    props = by_name["get_recalls"].parameters.get("properties", {})
    assert "store" not in props
    assert "limit" in props


async def test_heterogeneous_signatures_supported():
    """A tool with a different signature (topic, not limit) exposes its own
    params — proving the provider isn't locked to one tool shape."""

    async def get_news(store: FeedStore, topic: str) -> list[dict]:
        """Search public-health news for ``topic``."""
        return []

    provider = SourceProvider([get_news], FeedStore())
    (tool,) = await provider._list_tools()
    props = tool.parameters.get("properties", {})
    assert "topic" in props
    assert "store" not in props


def test_missing_docstring_raises():
    """A tool function without a docstring fails loudly at construction."""

    async def no_doc(store: FeedStore, limit: int = 20) -> list[dict]:
        return []

    with pytest.raises(ValueError, match="missing a docstring"):
        SourceProvider([no_doc], FeedStore())


async def test_namespaced_tool_callable(monkeypatch):
    """End-to-end: a SourceProvider tool is reachable under its namespace."""
    monkeypatch.setattr(fda_tools, "refresh_if_stale", AsyncMock(return_value=None))
    store = FeedStore()
    _seed_recall(store, "Prov recall")

    mcp = FastMCP("t")
    mcp.add_provider(SourceProvider(fda_tools.TOOL_FNS, store), namespace="fda")

    async with Client(mcp) as client:
        result = await client.call_tool("fda_get_recalls", {"limit": 5})

    text = " ".join(b.text for b in result.content if hasattr(b, "text"))
    assert "Prov recall" in text
