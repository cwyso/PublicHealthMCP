"""Article content fetching and extraction.

Source-agnostic helper for turning a web page into clean main-article text
(site chrome, navigation, and footers stripped) via :mod:`trafilatura`.

Robustness contract, mirroring :mod:`src.fda.ingestion`:
- :func:`extract_text` never raises; it returns ``None`` when extraction
  yields nothing.
- :func:`fetch_text` swallows :class:`httpx.HTTPError` (network errors,
  timeouts, non-2xx) and returns ``None`` (logged at WARNING).
"""

from __future__ import annotations

import logging

import httpx
import trafilatura

logger = logging.getLogger(__name__)

# Articles are full HTML pages (larger than the RSS feeds), so allow a bit more
# read budget than ingestion's feed timeout. Applied per-request so a caller's
# client without a timeout can't cause an indefinite hang.
DEFAULT_TIMEOUT = httpx.Timeout(10.0, connect=5.0)


def extract_text(html: str | bytes) -> str | None:
    """Extract clean main-article text from ``html``.

    Thin wrapper over :func:`trafilatura.extract`. Returns the extracted
    text, or ``None`` if extraction yields nothing (empty or boilerplate-only
    pages). Never raises.
    """
    try:
        text = trafilatura.extract(html)
    except Exception:
        logger.exception("trafilatura raised during extraction")
        return None
    if not text:
        return None
    return text


async def fetch_text(url: str, client: httpx.AsyncClient) -> str | None:
    """Fetch ``url`` and return its clean main-article text.

    Follows redirects (FDA RSS links are ``http://`` and 301 to ``https://``).
    Swallows :class:`httpx.HTTPError` and returns ``None`` (logged at WARNING),
    mirroring :func:`src.fda.ingestion.fetch_and_parse`. Pages that extract to
    nothing also yield ``None``.
    """
    try:
        response = await client.get(url, follow_redirects=True, timeout=DEFAULT_TIMEOUT)
        response.raise_for_status()
    except httpx.HTTPError as exc:
        logger.warning("article fetch failed for %s: %s", url, exc)
        return None
    return extract_text(response.text)
