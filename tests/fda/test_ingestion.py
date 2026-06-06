"""Tests for src.fda.ingestion: parsing, robustness, network errors, and the
TTL-aware FeedStore."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

import httpx
import pytest

from src.fda import ingestion
from src.fda.ingestion import (
    DEFAULT_TTL,
    FDA_FEEDS,
    FeedItem,
    FeedStore,
    fetch_and_parse,
    parse_feed,
    refresh_all,
    refresh_if_stale,
)

FIXTURES = Path(__file__).parent / "fixtures"


def _load_fixture(name: str) -> bytes:
    return (FIXTURES / name).read_bytes()


# --- Parsing real fixtures ----------------------------------------------------


@pytest.mark.parametrize(
    "source,fixture",
    [
        ("fda_recalls", "recalls.xml"),
        ("fda_drugs", "drugs.xml"),
        ("fda_medwatch", "medwatch.xml"),
    ],
)
def test_parse_real_fda_fixture(source: str, fixture: str) -> None:
    """Each captured FDA feed parses into a non-empty list of well-formed items."""
    items = parse_feed(source, _load_fixture(fixture))

    assert items, f"{source} produced no items from real fixture"
    for item in items:
        assert isinstance(item, FeedItem)
        assert item.source == source
        assert item.id and item.title and item.url
        assert item.published_at.tzinfo is not None, "datetime must be tz-aware"


# --- Robustness ---------------------------------------------------------------


def test_parse_skips_malformed_entry() -> None:
    """A feed with 2 valid + 1 broken item yields exactly the 2 valid items."""
    items = parse_feed("test", _load_fixture("malformed_entry.xml"))

    assert len(items) == 2
    titles = {i.title for i in items}
    assert titles == {"Valid item one", "Valid item two"}


def test_parse_returns_empty_on_garbage() -> None:
    """Non-XML garbage parses to []."""
    assert parse_feed("test", _load_fixture("garbage.xml")) == []


def test_parse_returns_empty_on_empty_body() -> None:
    """Empty bytes parse to []."""
    assert parse_feed("test", b"") == []


# --- Network errors -----------------------------------------------------------


def _mock_client(handler) -> httpx.AsyncClient:
    """AsyncClient whose every request runs through ``handler``."""
    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


async def test_fetch_and_parse_swallows_timeout() -> None:
    """A read timeout from the upstream yields [] instead of raising."""

    def handler(_request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("simulated read timeout")

    async with _mock_client(handler) as client:
        result = await fetch_and_parse(
            "fda_recalls", FDA_FEEDS["fda_recalls"], client=client
        )

    assert result == []


async def test_fetch_and_parse_swallows_5xx() -> None:
    """A 500 response yields [] (raise_for_status flows through HTTPError)."""

    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, text="oops")

    async with _mock_client(handler) as client:
        result = await fetch_and_parse(
            "fda_recalls", FDA_FEEDS["fda_recalls"], client=client
        )

    assert result == []


async def test_fetch_and_parse_swallows_connection_error() -> None:
    """A connection error from the transport yields []."""

    def handler(_request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("simulated connection refused")

    async with _mock_client(handler) as client:
        result = await fetch_and_parse(
            "fda_recalls", FDA_FEEDS["fda_recalls"], client=client
        )

    assert result == []


async def test_fetch_and_parse_happy_path_uses_supplied_client() -> None:
    """When the upstream responds with valid RSS, items come back parsed."""
    body = _load_fixture("recalls.xml")

    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=body)

    async with _mock_client(handler) as client:
        items = await fetch_and_parse(
            "fda_recalls", FDA_FEEDS["fda_recalls"], client=client
        )

    assert items
    assert all(i.source == "fda_recalls" for i in items)


# --- FeedStore ---------------------------------------------------------------


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


def test_store_get_is_empty_when_unpopulated() -> None:
    store = FeedStore()
    assert store.get() == []
    assert store.get(source="fda_recalls") == []


def test_store_get_filters_by_source_and_orders_newest_first() -> None:
    store = FeedStore()
    store.update("fda_recalls", [_make_item("fda_recalls", 1, age_minutes=10)])
    store.update(
        "fda_drugs",
        [
            _make_item("fda_drugs", 2, age_minutes=0),
            _make_item("fda_drugs", 3, age_minutes=20),
        ],
    )

    all_items = store.get()
    assert len(all_items) == 3
    # newest-first ordering across sources
    assert [i.title for i in all_items] == ["Item 2", "Item 1", "Item 3"]

    drugs_only = store.get(source="fda_drugs")
    assert {i.title for i in drugs_only} == {"Item 2", "Item 3"}


def test_store_get_since_filters_old_items() -> None:
    store = FeedStore()
    store.update(
        "fda_drugs",
        [
            _make_item("fda_drugs", 1, age_minutes=5),
            _make_item("fda_drugs", 2, age_minutes=60),
        ],
    )

    cutoff = datetime.now(timezone.utc) - timedelta(minutes=30)
    recent = store.get(since=cutoff)
    assert [i.title for i in recent] == ["Item 1"]


def test_store_is_stale_when_never_refreshed() -> None:
    store = FeedStore()
    assert store.is_stale("fda_recalls") is True
    assert store.last_refreshed("fda_recalls") is None


def test_store_is_stale_respects_ttl() -> None:
    store = FeedStore()
    store.update("fda_recalls", [])
    assert store.is_stale("fda_recalls", ttl=timedelta(minutes=15)) is False
    # A tiny TTL should report stale immediately (real elapsed time > 0).
    assert store.is_stale("fda_recalls", ttl=timedelta(microseconds=1)) is True


# --- Refresh orchestration ---------------------------------------------------


async def test_refresh_if_stale_skips_fresh_sources(monkeypatch) -> None:
    """Sources within their TTL window are not re-fetched."""
    store = FeedStore()
    store.update("fda_recalls", [_make_item("fda_recalls", 1)])
    # fda_drugs and fda_medwatch are stale (never refreshed); fda_recalls is fresh.

    fetched: list[str] = []

    async def fake_fetch_and_parse(source, url, **kwargs):
        fetched.append(source)
        return []

    monkeypatch.setattr(ingestion, "fetch_and_parse", fake_fetch_and_parse)

    await refresh_if_stale(store, ttl=DEFAULT_TTL)

    assert "fda_recalls" not in fetched
    assert set(fetched) == {"fda_drugs", "fda_medwatch"}


async def test_refresh_all_touches_every_source(monkeypatch) -> None:
    """refresh_all hits every configured feed regardless of staleness."""
    store = FeedStore()

    fetched: list[str] = []

    async def fake_fetch_and_parse(source, url, **kwargs):
        fetched.append(source)
        return []

    monkeypatch.setattr(ingestion, "fetch_and_parse", fake_fetch_and_parse)

    await refresh_all(store)

    assert set(fetched) == set(FDA_FEEDS.keys())
    for src in FDA_FEEDS:
        assert store.last_refreshed(src) is not None


async def test_refresh_reuses_provided_client_and_does_not_close_it(monkeypatch):
    """A supplied client is reused for fetches and left open (caller owns it)."""
    seen: list[httpx.AsyncClient] = []

    async def fake_fetch_and_parse(source, url, *, client=None):
        seen.append(client)
        return []

    monkeypatch.setattr(ingestion, "fetch_and_parse", fake_fetch_and_parse)

    caller_client = httpx.AsyncClient()
    await refresh_if_stale(
        FeedStore(), feeds={"fda_recalls": "http://x"}, client=caller_client
    )

    assert seen and all(c is caller_client for c in seen)
    assert not caller_client.is_closed  # refresh must not close a borrowed client
    await caller_client.aclose()
