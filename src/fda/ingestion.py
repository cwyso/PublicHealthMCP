"""FDA RSS feed ingestion.

Pure data layer: fetches FDA RSS feeds, parses entries into a normalized
:class:`FeedItem`, and exposes an in-memory :class:`FeedStore` with TTL-aware
refresh helpers.

Robustness contract:
- :func:`parse_feed` never raises — bad entries are skipped, a whole-feed
  failure yields ``[]``.
- :func:`fetch_and_parse` swallows network errors, timeouts, and 5xx
  (returns ``[]``); detect failures via :meth:`FeedStore.last_refreshed`.
"""

from __future__ import annotations

import calendar
import hashlib
import logging
from datetime import datetime, timedelta, timezone
from time import struct_time
from typing import Any

import feedparser
import httpx
from pydantic import BaseModel, ConfigDict, Field

logger = logging.getLogger(__name__)


# --- Source registry ----------------------------------------------------------

_FDA_BASE = "https://www.fda.gov/about-fda/contact-fda/stay-informed/rss-feeds"

FDA_FEEDS: dict[str, str] = {
    "fda_recalls": f"{_FDA_BASE}/recalls/rss.xml",
    "fda_drugs": f"{_FDA_BASE}/drugs/rss.xml",
    "fda_medwatch": f"{_FDA_BASE}/medwatch/rss.xml",
}

DEFAULT_TIMEOUT = httpx.Timeout(5.0, connect=5.0)
DEFAULT_TTL = timedelta(minutes=15)


# --- Data model ---------------------------------------------------------------


class FeedItem(BaseModel):
    """Normalized RSS feed entry.

    Immutable so consumers can rely on identity across refreshes when
    :attr:`id` matches.
    """

    model_config = ConfigDict(frozen=True)

    id: str
    source: str
    title: str
    summary: str
    url: str
    published_at: datetime
    raw: dict[str, Any] = Field(default_factory=dict)


# --- Fetch + parse ------------------------------------------------------------


async def fetch_feed(url: str, client: httpx.AsyncClient) -> bytes:
    """Fetch raw RSS body from ``url``.

    Raises whatever ``httpx`` raises on failure. Use :func:`fetch_and_parse`
    if you want network errors swallowed.
    """
    response = await client.get(url)
    response.raise_for_status()
    return response.content


def _struct_to_datetime(st: struct_time | None) -> datetime | None:
    """Convert feedparser's UTC-normalized struct_time to a tz-aware datetime.

    ``calendar.timegm`` (not ``time.mktime``) interprets the struct as UTC,
    which is what feedparser produces.
    """
    if st is None:
        return None
    return datetime.fromtimestamp(calendar.timegm(st), tz=timezone.utc)


def _entry_id(source: str, entry: Any) -> str | None:
    """Resolve a stable id for an entry.

    Prefers the feed-provided ``id``/``guid``; falls back to a hash of the
    link so the same item produces the same id across refreshes.
    """
    raw_id = entry.get("id") or entry.get("guid")
    if raw_id:
        return str(raw_id)
    link = entry.get("link")
    if link:
        digest = hashlib.sha1(f"{source}::{link}".encode()).hexdigest()
        return f"{source}::{digest}"
    return None


def parse_feed(source: str, body: bytes) -> list[FeedItem]:
    """Parse ``body`` into a list of :class:`FeedItem`.

    Never raises. Returns ``[]`` if the feed cannot be parsed at all.
    Individual entries that lack required fields are skipped (logged at
    DEBUG); per-entry conversion errors are logged at ERROR and skipped.
    """
    try:
        parsed = feedparser.parse(body)
    except Exception:
        logger.exception("feedparser raised while parsing source=%s", source)
        return []

    # feedparser sets bozo for any quirk, not just fatal ones; treat as a
    # failure only when there are also no entries to salvage.
    if parsed.bozo and not parsed.entries:
        logger.warning("feed %s appears malformed (no entries recovered)", source)
        return []

    items: list[FeedItem] = []
    for raw_entry in parsed.entries:
        try:
            entry_id = _entry_id(source, raw_entry)
            title = raw_entry.get("title")
            link = raw_entry.get("link")
            summary = raw_entry.get("summary") or raw_entry.get("description") or ""
            published = _struct_to_datetime(raw_entry.get("published_parsed"))

            if not (entry_id and title and link and published):
                logger.debug(
                    "skipping incomplete entry in %s "
                    "(has_id=%s, has_title=%s, has_link=%s, has_date=%s)",
                    source,
                    bool(entry_id),
                    bool(title),
                    bool(link),
                    bool(published),
                )
                continue

            items.append(
                FeedItem(
                    id=entry_id,
                    source=source,
                    title=str(title),
                    summary=str(summary),
                    url=str(link),
                    published_at=published,
                    raw=dict(raw_entry),
                )
            )
        except Exception:
            logger.exception("failed to convert entry in %s", source)
            continue

    return items


async def fetch_and_parse(
    source: str,
    url: str,
    *,
    client: httpx.AsyncClient | None = None,
    timeout: httpx.Timeout = DEFAULT_TIMEOUT,
) -> list[FeedItem]:
    """Fetch and parse a feed; swallow network errors and return ``[]``.

    Suitable for use from MCP tools where serving stale or empty data is
    preferred over crashing the request. If ``client`` is supplied the
    caller owns its lifecycle; otherwise a short-lived client is created.
    """
    owns_client = client is None
    if client is None:
        client = httpx.AsyncClient(timeout=timeout)
    try:
        body = await fetch_feed(url, client)
    except httpx.HTTPError as exc:
        logger.warning("fetch failed for %s (%s): %s", source, url, exc)
        return []
    finally:
        if owns_client:
            await client.aclose()
    return parse_feed(source, body)


# --- In-memory store with TTL -------------------------------------------------


class FeedStore:
    """In-memory cache of feed items, keyed by source.

    Not thread-safe. FastMCP runs an asyncio event loop, so single-thread
    semantics are sufficient as long as updates happen via awaited
    coroutines (which the refresh helpers ensure).
    """

    def __init__(self) -> None:
        self._items: dict[str, list[FeedItem]] = {}
        self._last_refreshed: dict[str, datetime] = {}

    def get(
        self,
        source: str | None = None,
        since: datetime | None = None,
    ) -> list[FeedItem]:
        """Return stored items, newest first.

        ``source``: if given, restrict to that source. Otherwise return items
        from every source.
        ``since``: if given, drop items older than this datetime.
        """
        if source is not None:
            items = list(self._items.get(source, []))
        else:
            items = [item for src_items in self._items.values() for item in src_items]
        if since is not None:
            items = [i for i in items if i.published_at >= since]
        items.sort(key=lambda i: i.published_at, reverse=True)
        return items

    def update(self, source: str, items: list[FeedItem]) -> None:
        """Replace stored items for ``source`` and stamp the refresh time."""
        self._items[source] = list(items)
        self._last_refreshed[source] = datetime.now(timezone.utc)

    def last_refreshed(self, source: str) -> datetime | None:
        return self._last_refreshed.get(source)

    def is_stale(self, source: str, ttl: timedelta = DEFAULT_TTL) -> bool:
        """True if ``source`` has never been refreshed or is older than ``ttl``."""
        last = self._last_refreshed.get(source)
        if last is None:
            return True
        return datetime.now(timezone.utc) - last > ttl


# --- Refresh orchestrators ----------------------------------------------------


async def refresh_all(
    store: FeedStore,
    feeds: dict[str, str] | None = None,
) -> None:
    """Refresh every source unconditionally."""
    feeds = feeds if feeds is not None else FDA_FEEDS
    async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT) as client:
        for source, url in feeds.items():
            items = await fetch_and_parse(source, url, client=client)
            store.update(source, items)


async def refresh_if_stale(
    store: FeedStore,
    ttl: timedelta = DEFAULT_TTL,
    feeds: dict[str, str] | None = None,
) -> None:
    """Refresh only sources whose cached data is older than ``ttl``."""
    feeds = feeds if feeds is not None else FDA_FEEDS
    stale = {src: url for src, url in feeds.items() if store.is_stale(src, ttl)}
    if not stale:
        return
    async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT) as client:
        for source, url in stale.items():
            items = await fetch_and_parse(source, url, client=client)
            store.update(source, items)
