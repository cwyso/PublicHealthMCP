"""Tests for the root FastMCP server.

Covers ``health_check``, that source tools register under their ``fda_`` prefix,
that the cross-source ``get_recent`` tool is present, and that a prefixed tool
is callable end-to-end through an injected, pre-populated store. Per-tool
behavior lives in tests/fda/test_tools.py and tests/test_aggregate.py.
"""

from datetime import datetime, timezone
from unittest.mock import AsyncMock

import pytest
from fastmcp import Client

from src import aggregate
from src.fda import tools as fda_tools
from src.fda.ingestion import FeedItem, FeedStore
from src.server import build_server, health_check, mcp

PREFIXED_FDA_TOOLS = {
    "fda_get_recalls",
    "fda_get_drug_updates",
    "fda_get_safety_alerts",
}


def _text(result) -> str:
    """Join the text content blocks of a tool-call result."""
    return " ".join(b.text for b in result.content if hasattr(b, "text"))


def test_health_check_returns_ok():
    """Direct call: ``health_check()`` returns the literal string ``"ok"``."""
    assert health_check() == "ok"


def test_server_has_expected_name():
    """The root MCP server instance is named ``"public-health-mcp"``."""
    assert mcp.name == "public-health-mcp"


async def test_health_check_callable_via_mcp_client():
    """End-to-end: ``health_check`` is reachable through the in-memory client."""
    async with Client(mcp) as client:
        result = await client.call_tool("health_check", {})
        text = next(
            (block.text for block in result.content if hasattr(block, "text")),
            None,
        )
        msg = f"expected 'ok', got {text!r} (full content: {result.content!r})"
        assert text == "ok", msg


async def test_unknown_tool_raises():
    """Unknown tool name raises instead of silently returning."""
    async with Client(mcp) as client:
        with pytest.raises(Exception):
            await client.call_tool("does_not_exist", {})


async def test_tools_registered():
    """FDA tools register under fda_ prefix; the cross-source get_recent is present."""
    async with Client(mcp) as client:
        names = {t.name for t in await client.list_tools()}

    missing = PREFIXED_FDA_TOOLS - names
    assert not missing, f"missing prefixed FDA tools: {missing}"
    assert "get_recent" in names
    # Bare core-function names must NOT be exposed as tools.
    assert "get_recalls" not in names
    assert "recent" not in names


async def test_prefixed_fda_tool_is_callable(monkeypatch):
    """A prefixed FDA tool is invokable through a server built on a seeded store.

    build_server(store) gives an isolated server bound to our store, so no
    global state leaks between tests. Refresh is stubbed (no network).
    """
    monkeypatch.setattr(fda_tools, "refresh_if_stale", AsyncMock(return_value=None))
    store = FeedStore()
    store.update(
        "fda_recalls",
        [
            FeedItem(
                id="fda_recalls-1",
                source="fda_recalls",
                title="Test recall",
                summary="...",
                url="https://example.com/fda_recalls/1",
                published_at=datetime.now(timezone.utc),
                raw={},
            )
        ],
    )
    server = build_server(store)

    async with Client(server) as client:
        result = await client.call_tool("fda_get_recalls", {"limit": 5})

    text_blocks = [b for b in result.content if hasattr(b, "text")]
    assert text_blocks, f"expected text content, got {result.content!r}"
    assert "Test recall" in text_blocks[0].text


async def test_get_recent_callable_spans_sources(monkeypatch):
    """get_recent reaches across sources end-to-end through the server."""
    monkeypatch.setattr(aggregate, "refresh_if_stale", AsyncMock(return_value=None))
    store = FeedStore()
    store.update(
        "fda_recalls",
        [
            FeedItem(
                id="r1",
                source="fda_recalls",
                title="Recall one",
                summary="...",
                url="https://example.com/r1",
                published_at=datetime.now(timezone.utc),
                raw={},
            )
        ],
    )
    store.update(
        "fda_drugs",
        [
            FeedItem(
                id="d1",
                source="fda_drugs",
                title="Drug update one",
                summary="...",
                url="https://example.com/d1",
                published_at=datetime.now(timezone.utc),
                raw={},
            )
        ],
    )
    server = build_server(store)

    async with Client(server) as client:
        result = await client.call_tool("get_recent", {"limit": 10})

    blob = _text(result)
    assert "Recall one" in blob and "Drug update one" in blob


async def test_all_tools_share_one_store(monkeypatch):
    """The core claim of the DI refactor: build_server wires ONE store into
    every tool. An item seeded once is visible through both a source-specific
    tool and the cross-source tool — which only holds if they share a store.
    """
    monkeypatch.setattr(fda_tools, "refresh_if_stale", AsyncMock(return_value=None))
    monkeypatch.setattr(aggregate, "refresh_if_stale", AsyncMock(return_value=None))
    store = FeedStore()
    store.update(
        "fda_recalls",
        [
            FeedItem(
                id="shared-1",
                source="fda_recalls",
                title="Shared recall",
                summary="...",
                url="https://example.com/shared-1",
                published_at=datetime.now(timezone.utc),
                raw={},
            )
        ],
    )
    server = build_server(store)

    async with Client(server) as client:
        via_source = await client.call_tool("fda_get_recalls", {"limit": 5})
        via_aggregate = await client.call_tool("get_recent", {"limit": 5})

    assert "Shared recall" in _text(via_source)
    assert "Shared recall" in _text(via_aggregate)
