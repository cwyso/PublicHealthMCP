"""Tests for src.article: trafilatura extraction and article fetching.

The HTML fixture is a real FDA recall page (captured via curl), so the
extraction tests prove that genuine site chrome is stripped, not just that the
wrapper runs.
"""

from __future__ import annotations

from pathlib import Path

import httpx
import pytest
import trafilatura

from src.article import extract_text, fetch_text

FIXTURES = Path(__file__).parent / "fixtures"

# Distinctive sentences from the recall body; survive HTML entity decoding.
ARTICLE_STRINGS = [
    "undeclared dark chocolate peanuts",
    "life-threatening allergic reaction",
]
# Header skip-links / nav chrome that must NOT appear in extracted text.
BOILERPLATE_STRINGS = [
    "Skip to main content",
    "Skip to FDA Search",
]


def _load_fixture(name: str) -> str:
    return (FIXTURES / name).read_text()


def _mock_client(handler) -> httpx.AsyncClient:
    """AsyncClient whose every request runs through ``handler``."""
    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


# --- extract_text -------------------------------------------------------------


def test_extract_text_keeps_body_and_strips_chrome() -> None:
    """Real article body survives; nav/header boilerplate is removed."""
    text = extract_text(_load_fixture("fda_article.html"))

    assert text is not None
    for needle in ARTICLE_STRINGS:
        assert needle in text, f"expected body text missing: {needle!r}"
    for boilerplate in BOILERPLATE_STRINGS:
        assert boilerplate not in text, f"chrome leaked through: {boilerplate!r}"


def test_extract_text_empty_bytes_returns_none() -> None:
    assert extract_text(b"") is None


def test_extract_text_empty_document_returns_none() -> None:
    assert extract_text("<html><body></body></html>") is None


def test_extract_text_returns_none_when_trafilatura_raises(monkeypatch) -> None:
    """The 'never raises' contract: an internal trafilatura error yields None."""

    def boom(*args, **kwargs):
        raise RuntimeError("trafilatura blew up")

    monkeypatch.setattr(trafilatura, "extract", boom)
    assert extract_text("<html><body>real content here</body></html>") is None


# --- fetch_text -------------------------------------------------------


async def test_fetch_text_happy_path() -> None:
    """A 200 with real HTML returns the extracted article text."""
    html = _load_fixture("fda_article.html")

    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text=html)

    async with _mock_client(handler) as client:
        text = await fetch_text("http://example.com/article", client)

    assert text is not None
    assert "undeclared dark chocolate peanuts" in text


@pytest.mark.parametrize("status", [404, 500])
async def test_fetch_text_swallows_error_status(status: int) -> None:
    """Non-2xx responses yield None (raise_for_status -> HTTPError)."""

    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(status, text="error")

    async with _mock_client(handler) as client:
        result = await fetch_text("http://example.com/x", client)

    assert result is None


async def test_fetch_text_swallows_read_timeout() -> None:
    """A read timeout yields None instead of raising."""

    def handler(_request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("simulated read timeout")

    async with _mock_client(handler) as client:
        result = await fetch_text("http://example.com/x", client)

    assert result is None


async def test_fetch_text_swallows_connect_error() -> None:
    """A connection error yields None."""

    def handler(_request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("simulated connection refused")

    async with _mock_client(handler) as client:
        result = await fetch_text("http://example.com/x", client)

    assert result is None


async def test_fetch_text_empty_extraction_returns_none() -> None:
    """A 200 page that extracts to nothing yields None."""

    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text="<html><body></body></html>")

    async with _mock_client(handler) as client:
        result = await fetch_text("http://example.com/empty", client)

    assert result is None
