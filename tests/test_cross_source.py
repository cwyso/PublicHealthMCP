"""Tests for src.cross_source (cross-source tools).

The point of these tests: prove ``get_recent`` genuinely spans sources, not
just FDA. We seed a fake second source (``cdc_test``) directly into the shared
store — which works today because FeedStore is keyed by source and aggregates
across all of them — and assert ``recent`` merges and orders across both.
"""

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock

import pytest

from src import cross_source
from src.cross_source import recent
from src.fda.ingestion import FeedItem, FeedStore


@pytest.fixture
def store(monkeypatch):
    """A fresh FeedStore with refresh_if_stale stubbed (no network)."""
    monkeypatch.setattr(cross_source, "refresh_if_stale", AsyncMock(return_value=None))
    return FeedStore()


def _make_item(source: str, n: int, age_minutes: int = 0) -> FeedItem:
    return FeedItem(
        id=f"{source}-{n}",
        source=source,
        title=f"{source} item {n}",
        summary="...",
        url=f"https://example.com/{source}/{n}",
        published_at=datetime.now(timezone.utc) - timedelta(minutes=age_minutes),
        raw={},
    )


async def test_recent_spans_multiple_sources(store):
    """recent() merges items from every source, newest first."""
    store.update("fda_recalls", [_make_item("fda_recalls", 1, age_minutes=10)])
    store.update("cdc_test", [_make_item("cdc_test", 1, age_minutes=5)])

    result = await recent(store)

    assert {r["source"] for r in result} == {"fda_recalls", "cdc_test"}
    # cdc_test item is newer (5 min old vs 10), so it sorts first.
    assert result[0]["source"] == "cdc_test"


async def test_recent_filters_by_sources(store):
    """recent(sources=[...]) restricts to the requested source keys."""
    store.update("fda_recalls", [_make_item("fda_recalls", 1)])
    store.update("cdc_test", [_make_item("cdc_test", 1)])

    result = await recent(store, sources=["cdc_test"])

    assert {r["source"] for r in result} == {"cdc_test"}


async def test_recent_respects_limit(store):
    """recent() caps the merged result at ``limit``."""
    store.update("fda_recalls", [_make_item("fda_recalls", i) for i in range(5)])
    store.update("cdc_test", [_make_item("cdc_test", i) for i in range(5)])

    result = await recent(store, limit=3)
    assert len(result) == 3


async def test_recent_clamps_nonpositive_limit(store):
    """limit <= 0 yields an empty list."""
    store.update("fda_recalls", [_make_item("fda_recalls", 1)])

    assert await recent(store, limit=0) == []
    assert await recent(store, limit=-2) == []


async def test_recent_empty_store(store):
    """An empty store yields []."""
    assert await recent(store) == []
