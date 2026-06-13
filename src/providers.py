"""Generic source provider.

One :class:`Provider` reused by every source. A source contributes a list of
tool functions — each taking the shared store as its first argument and carrying
a docstring — and ``SourceProvider`` binds the store and exposes them as MCP
tools:

- the tool name comes from each function's ``__name__`` (no hardcoded strings),
- the description comes from its docstring (single-sourced, shipped to clients),
- any remaining parameters become the tool's input schema.

Because the binding is by ``functools.partial`` and the schema is introspected,
sources with different tool signatures (``limit`` for FDA, ``topic`` for news,
…) all work through the same provider. Register one per source under its own
namespace (see ``src/server.py``).
"""

import functools
from collections.abc import Awaitable, Callable, Sequence

from fastmcp.server.providers import Provider
from fastmcp.tools import Tool

from src.fda.ingestion import FeedStore

# Tool functions are async, take the shared store first, and return the
# JSON-serializable item list. The remaining params become the tool schema.
ToolFn = Callable[..., Awaitable[list[dict]]]


class SourceProvider(Provider):
    """Exposes a source's store-bound tool functions as MCP tools."""

    def __init__(self, fns: Sequence[ToolFn], store: FeedStore) -> None:
        super().__init__()
        tools: list[Tool] = []
        for fn in fns:
            if not fn.__doc__:
                # FastMCP ships the description to clients; a missing docstring
                # would silently produce a description-less tool.
                raise ValueError(f"tool {fn.__name__!r} is missing a docstring")
            tools.append(
                Tool.from_function(
                    functools.partial(fn, store),
                    name=fn.__name__,
                    description=fn.__doc__,
                )
            )
        self._tools = tools

    async def _list_tools(self) -> Sequence[Tool]:
        return self._tools
