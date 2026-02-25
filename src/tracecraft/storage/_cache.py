"""
Shared TTL in-memory cache for remote trace store backends.

Prevents excessive API calls when the TUI polls frequently.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from tracecraft.core.models import AgentRun


@dataclass
class _CachedPage:
    """A cached list of AgentRun objects with a fetch timestamp."""

    data: list[AgentRun]
    fetched_at: float = field(default_factory=time.monotonic)


class TTLCache:
    """
    Simple TTL-based in-memory cache for lists of AgentRun objects.

    Used by remote trace store backends (X-Ray, Cloud Trace, Azure Monitor,
    DataDog) to avoid hammering platform APIs when the TUI polls frequently.

    Example:
        cache = TTLCache(ttl_seconds=60)
        data = cache.get("list_all")
        if data is None:
            data = fetch_from_api()
            cache.set("list_all", data)
    """

    def __init__(self, ttl_seconds: int = 60) -> None:
        """
        Initialize the cache.

        Args:
            ttl_seconds: How long cached entries remain valid. Defaults to 60s.
        """
        self._ttl = ttl_seconds
        self._store: dict[str, _CachedPage] = {}

    def get(self, key: str) -> list[AgentRun] | None:
        """
        Retrieve cached data for a key.

        Args:
            key: Cache key string.

        Returns:
            Cached list of AgentRun objects, or None if miss or expired.
        """
        entry = self._store.get(key)
        if entry is None:
            return None
        age = time.monotonic() - entry.fetched_at
        if age >= self._ttl:
            del self._store[key]
            return None
        return entry.data

    def set(self, key: str, data: list[AgentRun]) -> None:
        """
        Store data in the cache under a key.

        Args:
            key: Cache key string.
            data: List of AgentRun objects to cache.
        """
        self._store[key] = _CachedPage(data=data)

    def invalidate(self, key: str | None = None) -> None:
        """
        Invalidate one or all cache entries.

        Args:
            key: Specific key to invalidate, or None to clear all entries.
        """
        if key is None:
            self._store.clear()
        else:
            self._store.pop(key, None)
