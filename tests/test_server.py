"""Tests for the bare-bones FastMCP server."""

import pytest
from fastmcp import Client

from src.server import health_check, mcp


def test_health_check_returns_ok():
    """Direct call: ``health_check()`` returns the literal string ``"ok"``."""
    assert health_check() == "ok"


def test_server_has_expected_name():
    """The MCP server instance is named ``"public-health-mcp"``."""
    assert mcp.name == "public-health-mcp"


async def test_health_check_callable_via_mcp_client():
    """End-to-end: the tool is reachable through the FastMCP in-memory client.

    This is the test that actually proves the ``@mcp.tool()`` registration
    worked. A passing direct call would not catch a misregistered tool.
    """
    async with Client(mcp) as client:
        result = await client.call_tool("health_check", {})
        # FastMCP wraps text returns in content blocks; pull the text out
        text = next(
            (block.text for block in result.content if hasattr(block, "text")),
            None,
        )
        msg = f"expected 'ok', got {text!r} (full content: {result.content!r})"
        assert text == "ok", msg


async def test_unknown_tool_raises():
    """Unknown tool name raises an error instead of silently returning."""
    async with Client(mcp) as client:
        with pytest.raises(Exception):
            await client.call_tool("does_not_exist", {})
