"""Tests for the history store using a mock database."""
import pytest
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

try:
    from .history import HistoryStore
    from .database import Database
    from .datamodels.location import Location
except ImportError:
    from history import HistoryStore
    from database import Database
    from datamodels.location import Location


class MockDatabase:
    """In-memory mock that simulates Database for testing."""

    def __init__(self):
        self._available = True
        self._locations = {}  # (lat, lon) -> id
        self._routes = {}     # name -> {id, src_id, dst_id}
        self._records = []    # list of dicts
        self._next_loc_id = 1
        self._next_route_id = 1
        self._next_record_id = 1

    def is_available(self):
        return self._available

    def execute(self, query, params=None):
        return 1

    def fetch_one(self, query, params=None):
        query_lower = query.strip().lower()
        if "from locations" in query_lower:
            lat, lon = params[0], params[1]
            key = (lat, lon)
            if key in self._locations:
                return {"id": self._locations[key]}
            return None
        if "from routes" in query_lower:
            name = params[0]
            if name in self._routes:
                return {"id": self._routes[name]["id"]}
            return None
        return None

    def fetch_all(self, query, params=None):
        return []


class TestHistoryStore:
    def setup_method(self):
        self.db = MockDatabase()
        self.store = HistoryStore(self.db)

    def test_get_or_create_location_new(self):
        loc = Location(40.85, -73.96, "Test Location")
        # First call returns None (not found), so it inserts.
        # After insert, second fetch_one should find it.
        # We simulate by adding to mock after the first fetch_one call.
        original_fetch_one = self.db.fetch_one

        call_count = {"n": 0}

        def patched_fetch_one(query, params=None):
            call_count["n"] += 1
            if call_count["n"] == 1:
                return None  # Not found yet
            # After insert
            self.db._locations[(loc.lat, loc.lon)] = 1
            return {"id": 1}

        self.db.fetch_one = patched_fetch_one
        result = self.store._get_or_create_location(loc)
        assert result == 1

    def test_record_duration_when_db_unavailable(self):
        self.db._available = False
        loc_src = Location(40.85, -73.96, "Src")
        loc_dst = Location(40.84, -73.94, "Dst")
        result = self.store.record_duration("test_route", loc_src, loc_dst, 600)
        assert result is False

    def test_get_best_times_when_db_unavailable(self):
        self.db._available = False
        result = self.store.get_best_times("test_route")
        assert result == []

    def test_get_time_series_when_db_unavailable(self):
        self.db._available = False
        result = self.store.get_time_series("test_route")
        assert result == []

    def test_get_routes_when_db_unavailable(self):
        self.db._available = False
        result = self.store.get_routes()
        assert result == []

    def test_get_daily_summary_when_db_unavailable(self):
        self.db._available = False
        result = self.store.get_daily_summary("test_route")
        assert result == []


class TestDatabaseModule:
    def test_database_no_url(self):
        """Database should gracefully handle missing DATABASE_URL."""
        with patch.dict("os.environ", {}, clear=True):
            db = Database()
            assert db.is_available() is False
            assert db.execute("SELECT 1") is None
            assert db.fetch_all("SELECT 1") == []
            assert db.fetch_one("SELECT 1") is None

    def test_health_check_no_connection(self):
        with patch.dict("os.environ", {}, clear=True):
            db = Database()
            health = db.health_check()
            assert health["healthy"] is False
