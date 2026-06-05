"""Tests for the FDA MCP tool core functions (src.fda.tools).

The core functions take a ``FeedStore`` directly, so tests inject a store
rather than monkeypatching a module global. ``refresh_if_stale`` is stubbed to
keep tests offline. End-to-end reachability through the server (under the
``fda_`` names) is covered in tests/test_server.py.
"""

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock

import pytest

from src.fda import tools as fda_tools
from src.fda.ingestion import FeedItem, FeedStore
from src.fda.tools import get_drug_updates, get_recalls, get_safety_alerts

# (source key, core tool function) pairs for parametrized tests.
FDA_TOOLS = [
    ("fda_recalls", get_recalls),
    ("fda_drugs", get_drug_updates),
    ("fda_medwatch", get_safety_alerts),
]


@pytest.fixture
def store(monkeypatch):
    """A fresh FeedStore with refresh_if_stale stubbed (no network)."""
    monkeypatch.setattr(fda_tools, "refresh_if_stale", AsyncMock(return_value=None))
    return FeedStore()


def _make_item(source: str, n: int, age_minutes: int = 0) -> FeedItem:
    return FeedItem(
        id=f"{source}-{n}",
        source=source,
        title=f"Item {n}",
        summary="...",
        url=f"https://example.com/{source}/{n}",
        published_at=datetime.now(timezone.utc) - timedelta(minutes=age_minutes),
        raw={},
    )


@pytest.mark.parametrize("source,tool", FDA_TOOLS)
async def test_tool_returns_serialized_items(store, source, tool):
    """Each FDA tool returns its source's items as JSON-serializable dicts."""
    store.update(source, [_make_item(source, i) for i in range(5)])

    result = await tool(store)

    assert isinstance(result, list)
    assert len(result) == 5
    for entry in result:
        assert isinstance(entry, dict)
        assert entry["source"] == source
        assert "id" in entry and "title" in entry and "url" in entry
        # mode="json" must serialize datetime to an ISO 8601 string
        assert isinstance(entry["published_at"], str)


@pytest.mark.parametrize("source,tool", FDA_TOOLS)
async def test_tool_respects_limit(store, source, tool):
    """Each tool caps results at ``limit``."""
    store.update(source, [_make_item(source, i) for i in range(30)])

    result = await tool(store, limit=10)
    assert len(result) == 10


@pytest.mark.parametrize("source,tool", FDA_TOOLS)
async def test_tool_returns_empty_when_no_items(store, source, tool):
    """An empty store yields ``[]`` (no crash, no ``None``)."""
    result = await tool(store)
    assert result == []


@pytest.mark.parametrize("source,tool", FDA_TOOLS)
async def test_tool_clamps_nonpositive_limit(store, source, tool):
    """``limit <= 0`` yields ``[]`` rather than dropping items off the end."""
    store.update(source, [_make_item(source, i) for i in range(5)])

    assert await tool(store, limit=0) == []
    assert await tool(store, limit=-3) == []


@pytest.mark.parametrize("source,tool", FDA_TOOLS)
async def test_tool_triggers_refresh(monkeypatch, source, tool):
    """Each tool awaits ``refresh_if_stale`` exactly once per call."""
    refresh_mock = AsyncMock(return_value=None)
    monkeypatch.setattr(fda_tools, "refresh_if_stale", refresh_mock)

    await tool(FeedStore())
    refresh_mock.assert_awaited_once()


async def test_tools_only_return_their_own_source(store):
    """Cross-contamination check: one tool's results never include another's."""
    store.update("fda_recalls", [_make_item("fda_recalls", 1)])
    store.update("fda_drugs", [_make_item("fda_drugs", 2)])
    store.update("fda_medwatch", [_make_item("fda_medwatch", 3)])

    recalls = await get_recalls(store)
    drugs = await get_drug_updates(store)
    alerts = await get_safety_alerts(store)

    assert {r["source"] for r in recalls} == {"fda_recalls"}
    assert {d["source"] for d in drugs} == {"fda_drugs"}
    assert {a["source"] for a in alerts} == {"fda_medwatch"}
