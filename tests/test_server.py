"""Tests for the root FastMCP server.

Covers the root server's own tool (``health_check``) and that the FDA tools
are registered under their ``fda_``-prefixed names. Per-tool behavior is
tested in tests/fda/test_tools.py.
"""

from datetime import datetime, timezone
from unittest.mock import AsyncMock

import pytest
from fastmcp import Client

from src.fda import tools as fda_tools
from src.fda.ingestion import FeedItem, FeedStore
from src.server import health_check, mcp

PREFIXED_FDA_TOOLS = {
    "fda_get_recalls",
    "fda_get_drug_updates",
    "fda_get_safety_alerts",
}


# --- health_check -------------------------------------------------------------


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


# --- FDA tool registration ----------------------------------------------------


async def test_fda_tools_registered_with_prefix():
    """The FDA tools are exposed through the root server with the fda_ prefix.

    Proves register_fda(mcp) attached the tools under their prefixed names and
    that the bare function names do not leak onto the server.
    """
    async with Client(mcp) as client:
        tools = await client.list_tools()
    names = {t.name for t in tools}

    missing = PREFIXED_FDA_TOOLS - names
    assert not missing, f"missing prefixed FDA tools: {missing}"
    # The bare function names must NOT be exposed as tools.
    assert "get_recalls" not in names


async def test_prefixed_fda_tool_is_callable(monkeypatch):
    """A prefixed FDA tool can be invoked through the root server.

    Stubs refresh (no network) and seeds the store so the call returns data.
    """
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
    monkeypatch.setattr(fda_tools, "_store", store)
    monkeypatch.setattr(fda_tools, "refresh_if_stale", AsyncMock(return_value=None))

    async with Client(mcp) as client:
        result = await client.call_tool("fda_get_recalls", {"limit": 5})

    text_blocks = [b for b in result.content if hasattr(b, "text")]
    assert text_blocks, f"expected text content, got {result.content!r}"
    assert "Test recall" in text_blocks[0].text
