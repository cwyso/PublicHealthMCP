"""FDA source as a FastMCP custom Provider.

Models the FDA source as a first-class, self-describing unit: it supplies its
own tools and owns its own resource lifecycle. Registered with
``namespace="fda"`` (see ``src/server.py``), so the bare tool names here are
exposed to clients as ``fda_get_recalls`` etc.

The provider owns one ``httpx.AsyncClient`` for its lifetime via ``lifespan()``,
reused across refreshes instead of opening a connection pool per call. Tool
wrappers read that client *lazily* at call time, because ``lifespan`` runs
after ``_list_tools`` and sets the client then.
"""

from collections.abc import AsyncIterator, Sequence
from contextlib import asynccontextmanager

import httpx
from fastmcp.server.providers import Provider
from fastmcp.tools import Tool

from src.fda import tools
from src.fda.ingestion import DEFAULT_TIMEOUT, FeedStore


class FDAProvider(Provider):
    """Supplies the FDA tools, bound to a shared store, with a lifespan client."""

    def __init__(self, store: FeedStore) -> None:
        super().__init__()
        self._store = store
        self._client: httpx.AsyncClient | None = None

    @asynccontextmanager
    async def lifespan(self) -> AsyncIterator[None]:
        """Open one httpx client on startup; close it on shutdown."""
        self._client = httpx.AsyncClient(timeout=DEFAULT_TIMEOUT)
        try:
            yield
        finally:
            await self._client.aclose()
            self._client = None

    async def _list_tools(self) -> Sequence[Tool]:
        # Bare names; namespace="fda" at registration adds the fda_ prefix.
        # Descriptions are single-sourced from the core functions' docstrings.
        specs = [
            (self._get_recalls, "get_recalls", tools.get_recalls),
            (self._get_drug_updates, "get_drug_updates", tools.get_drug_updates),
            (self._get_safety_alerts, "get_safety_alerts", tools.get_safety_alerts),
        ]
        built: list[Tool] = []
        for wrapper, name, core in specs:
            if not core.__doc__:
                # FastMCP exposes the description to clients; a None here would
                # silently ship a description-less tool. Fail loudly instead.
                raise ValueError(f"core function for {name!r} is missing a docstring")
            built.append(Tool.from_function(wrapper, name=name, description=core.__doc__))
        return built

    # Thin wrappers. Bound-method signature is (limit: int = 20) — what the tool
    # schema exposes. Each reads self._client live so the lifespan client is
    # used when present, and refresh falls back to its own client otherwise.
    async def _get_recalls(self, limit: int = 20) -> list[dict]:
        return await tools.get_recalls(self._store, limit, client=self._client)

    async def _get_drug_updates(self, limit: int = 20) -> list[dict]:
        return await tools.get_drug_updates(self._store, limit, client=self._client)

    async def _get_safety_alerts(self, limit: int = 20) -> list[dict]:
        return await tools.get_safety_alerts(self._store, limit, client=self._client)
