"""
Tests for the shared TTLCache utility.
"""

from __future__ import annotations

import time

from tracecraft.core.models import AgentRun
from tracecraft.storage._cache import TTLCache


def _make_run(name: str = "test-run") -> AgentRun:
    """Create a minimal AgentRun for cache testing."""
    from datetime import UTC, datetime

    return AgentRun(name=name, start_time=datetime.now(UTC))


class TestTTLCacheMiss:
    def test_cache_miss_returns_none(self):
        """Cache returns None for a key that has never been set."""
        cache = TTLCache(ttl_seconds=60)
        assert cache.get("nonexistent") is None

    def test_cache_miss_returns_none_after_expiry(self):
        """Cache returns None when TTL is 0 (immediately expired)."""
        cache = TTLCache(ttl_seconds=0)
        run = _make_run()
        cache.set("key", [run])
        # With ttl=0, any subsequent get should expire
        time.sleep(0.01)
        assert cache.get("key") is None


class TestTTLCacheHit:
    def test_cache_hit_returns_data(self):
        """Cache returns stored data on hit."""
        cache = TTLCache(ttl_seconds=60)
        run = _make_run("my-run")
        cache.set("list_all", [run])

        result = cache.get("list_all")

        assert result is not None
        assert len(result) == 1
        assert result[0].name == "my-run"

    def test_cache_hit_returns_same_list_object(self):
        """Cache returns the same list instance (no copy)."""
        cache = TTLCache(ttl_seconds=60)
        runs = [_make_run("a"), _make_run("b")]
        cache.set("key", runs)

        result = cache.get("key")
        assert result is runs

    def test_cache_stores_empty_list(self):
        """Cache correctly stores and returns an empty list."""
        cache = TTLCache(ttl_seconds=60)
        cache.set("empty", [])

        result = cache.get("empty")
        assert result is not None
        assert result == []

    def test_multiple_keys_independent(self):
        """Different keys are stored and retrieved independently."""
        cache = TTLCache(ttl_seconds=60)
        runs_a = [_make_run("a")]
        runs_b = [_make_run("b"), _make_run("c")]
        cache.set("key_a", runs_a)
        cache.set("key_b", runs_b)

        assert cache.get("key_a") == runs_a
        assert cache.get("key_b") == runs_b


class TestTTLCacheExpiry:
    def test_cache_expires_after_ttl(self):
        """Cache entry expires after the configured TTL."""
        cache = TTLCache(ttl_seconds=0)
        run = _make_run()
        cache.set("key", [run])
        time.sleep(0.01)

        # Should be expired
        assert cache.get("key") is None

    def test_cache_does_not_expire_before_ttl(self):
        """Cache entry is valid before TTL elapses."""
        cache = TTLCache(ttl_seconds=3600)  # 1 hour
        run = _make_run()
        cache.set("key", [run])

        # Should still be valid
        assert cache.get("key") is not None

    def test_expired_entry_removed_on_get(self):
        """Getting an expired entry removes it from the internal store."""
        cache = TTLCache(ttl_seconds=0)
        cache.set("key", [_make_run()])
        time.sleep(0.01)

        cache.get("key")  # triggers removal

        # Direct internal check: entry should be gone
        assert "key" not in cache._store


class TestTTLCacheInvalidate:
    def test_invalidate_single_key(self):
        """Invalidating a specific key removes only that key."""
        cache = TTLCache(ttl_seconds=60)
        cache.set("key1", [_make_run("a")])
        cache.set("key2", [_make_run("b")])

        cache.invalidate("key1")

        assert cache.get("key1") is None
        assert cache.get("key2") is not None

    def test_invalidate_nonexistent_key_is_safe(self):
        """Invalidating a key that was never set does not raise."""
        cache = TTLCache(ttl_seconds=60)
        cache.invalidate("never_set")  # should not raise

    def test_invalidate_all_keys(self):
        """Calling invalidate(None) clears all entries."""
        cache = TTLCache(ttl_seconds=60)
        cache.set("a", [_make_run("x")])
        cache.set("b", [_make_run("y")])
        cache.set("c", [_make_run("z")])

        cache.invalidate()

        assert cache.get("a") is None
        assert cache.get("b") is None
        assert cache.get("c") is None
        assert len(cache._store) == 0

    def test_invalidate_after_set_allows_fresh_set(self):
        """After invalidation, setting a key again works correctly."""
        cache = TTLCache(ttl_seconds=60)
        cache.set("key", [_make_run("old")])
        cache.invalidate("key")

        new_runs = [_make_run("new")]
        cache.set("key", new_runs)

        result = cache.get("key")
        assert result is not None
        assert result[0].name == "new"
