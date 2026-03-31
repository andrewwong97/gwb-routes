"""Unit tests for RoutesCache – key sanitization and recommendation roundtrip.

Uses a simple in-memory dict that mimics the Redis get/setex/keys/delete
contract so no real Redis instance is needed.
"""

import json
import pytest
from unittest.mock import patch

from routes_cache import RoutesCache
from datamodels.location import Location


# ── In-memory Redis fake ────────────────────────────────────────────────

class FakeRedis:
    """Minimal Redis stand-in backed by a plain dict."""

    def __init__(self):
        self.store: dict[str, bytes] = {}

    def get(self, key: str):
        return self.store.get(key)

    def setex(self, key: str, ttl: int, value):
        # Real Redis stores bytes; mirror that.
        if isinstance(value, str):
            value = value.encode()
        self.store[key] = value

    def keys(self, pattern: str = "*"):
        import fnmatch
        return [k for k in self.store if fnmatch.fnmatch(k, pattern)]

    def delete(self, *keys):
        count = 0
        for k in keys:
            if k in self.store:
                del self.store[k]
                count += 1
        return count

    def ping(self):
        return True

    def info(self):
        return {"used_memory_human": "0B"}


def _make_cache(fake_redis=None):
    """Build a RoutesCache wired to a FakeRedis (skips real connection)."""
    cache = RoutesCache.__new__(RoutesCache)
    cache.redis = fake_redis or FakeRedis()
    cache.cache_ttl = 180
    cache.recommendation_ttl = 120
    cache.redis_url = "fake://localhost"
    return cache


# ── Key sanitization ────────────────────────────────────────────────────

class TestSanitizeKeyPart:
    def test_replaces_colons(self):
        assert RoutesCache._sanitize_key_part("foo:bar") == "foo_bar"

    def test_replaces_pipes(self):
        assert RoutesCache._sanitize_key_part("foo|bar") == "foo_bar"

    def test_strips_whitespace(self):
        assert RoutesCache._sanitize_key_part("  hello  ") == "hello"

    def test_truncates_long_values(self):
        long_val = "a" * 300
        assert len(RoutesCache._sanitize_key_part(long_val)) == 200

    def test_plain_address_unchanged(self):
        assert RoutesCache._sanitize_key_part("123 Main St, NJ") == "123 Main St, NJ"


class TestRecommendationKey:
    def test_basic_key_structure(self):
        key = RoutesCache._recommendation_key("Fort Lee, NJ", "Manhattan, NY")
        assert key.startswith("recommend:")
        assert "|" in key  # delimiter between origin and destination

    def test_colons_in_input_do_not_break_prefix(self):
        key = RoutesCache._recommendation_key("a:b:c", "d:e")
        # Only the first 'recommend:' colon should exist as a colon
        parts = key.split(":")
        assert parts[0] == "recommend"
        # The remainder should have no extra colons
        rest = ":".join(parts[1:])
        assert ":" not in rest

    def test_same_inputs_produce_same_key(self):
        k1 = RoutesCache._recommendation_key("A", "B")
        k2 = RoutesCache._recommendation_key("A", "B")
        assert k1 == k2

    def test_different_inputs_produce_different_keys(self):
        k1 = RoutesCache._recommendation_key("A", "B")
        k2 = RoutesCache._recommendation_key("A", "C")
        assert k1 != k2


# ── Recommendation roundtrip ────────────────────────────────────────────

class TestRecommendationRoundtrip:
    def test_set_then_get_returns_same_data(self):
        cache = _make_cache()
        data = {"recommended_level": "upper", "direction": "NJ → NYC"}

        cache.set_recommendation("Fort Lee, NJ", "Manhattan, NY", data)
        result = cache.get_recommendation("Fort Lee, NJ", "Manhattan, NY")

        assert result == data

    def test_get_missing_returns_none(self):
        cache = _make_cache()
        assert cache.get_recommendation("nowhere", "nothing") is None

    def test_different_destinations_do_not_collide(self):
        cache = _make_cache()
        data_a = {"level": "upper"}
        data_b = {"level": "lower"}

        cache.set_recommendation("Fort Lee, NJ", "Manhattan, NY", data_a)
        cache.set_recommendation("Fort Lee, NJ", "Brooklyn, NY", data_b)

        assert cache.get_recommendation("Fort Lee, NJ", "Manhattan, NY") == data_a
        assert cache.get_recommendation("Fort Lee, NJ", "Brooklyn, NY") == data_b

    def test_inputs_with_special_chars_roundtrip(self):
        cache = _make_cache()
        data = {"level": "lower"}

        origin = "123:Main|St, NJ"
        dest = "456:Broadway|Ave, NY"

        cache.set_recommendation(origin, dest, data)
        assert cache.get_recommendation(origin, dest) == data

    def test_partial_invalidation_by_origin(self):
        """Keys should support pattern-based deletion for a specific origin."""
        cache = _make_cache()
        cache.set_recommendation("Fort Lee, NJ", "Manhattan, NY", {"a": 1})
        cache.set_recommendation("Fort Lee, NJ", "Brooklyn, NY", {"b": 2})
        cache.set_recommendation("Hoboken, NJ", "Manhattan, NY", {"c": 3})

        # Delete all recommendations originating from Fort Lee
        keys = cache.redis.keys("recommend:Fort Lee*")
        assert len(keys) == 2
        cache.redis.delete(*keys)

        # Fort Lee entries gone, Hoboken entry remains
        assert cache.get_recommendation("Fort Lee, NJ", "Manhattan, NY") is None
        assert cache.get_recommendation("Fort Lee, NJ", "Brooklyn, NY") is None
        assert cache.get_recommendation("Hoboken, NJ", "Manhattan, NY") == {"c": 3}


# ── Route cache roundtrip ───────────────────────────────────────────────

class TestRouteCacheRoundtrip:
    def test_set_then_get_returns_duration(self):
        cache = _make_cache()
        origin = Location(40.85, -73.96, "GWB NJ")
        dest = Location(40.84, -73.94, "GWB NYC")

        cache.set(origin, dest, "15 mins")
        result = cache.get(origin, dest)

        assert result == "15 mins"

    def test_get_missing_returns_none(self):
        cache = _make_cache()
        origin = Location(40.85, -73.96, "A")
        dest = Location(40.84, -73.94, "B")

        assert cache.get(origin, dest) is None
