import os
import logging
from datetime import datetime, timezone

log = logging.getLogger(__name__)

try:
    import psycopg2
    from psycopg2.extras import RealDictCursor
except ImportError:
    psycopg2 = None
    RealDictCursor = None
    log.warning("psycopg2 not installed, database features will be disabled")


SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS locations (
    id SERIAL PRIMARY KEY,
    lat DOUBLE PRECISION NOT NULL,
    lon DOUBLE PRECISION NOT NULL,
    name VARCHAR(255),
    UNIQUE(lat, lon)
);

CREATE TABLE IF NOT EXISTS routes (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL UNIQUE,
    src_id INTEGER REFERENCES locations(id),
    dst_id INTEGER REFERENCES locations(id)
);

CREATE TABLE IF NOT EXISTS duration_records (
    id SERIAL PRIMARY KEY,
    route_id INTEGER REFERENCES routes(id) NOT NULL,
    duration_seconds INTEGER NOT NULL,
    captured_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    day_of_week SMALLINT NOT NULL,
    hour_of_day SMALLINT NOT NULL,
    minute_bucket SMALLINT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_duration_route_dow
    ON duration_records(route_id, day_of_week);
CREATE INDEX IF NOT EXISTS idx_duration_route_time
    ON duration_records(route_id, day_of_week, hour_of_day, minute_bucket);
CREATE INDEX IF NOT EXISTS idx_duration_captured
    ON duration_records(captured_at);
"""


class Database:
    """PostgreSQL connection manager for persistent historical data."""

    def __init__(self):
        self.database_url = os.getenv("DATABASE_URL")
        self.conn = None

        if not self.database_url:
            log.warning("DATABASE_URL is not set, database features will be disabled")
            return

        if psycopg2 is None:
            log.warning("psycopg2 not available, database features will be disabled")
            return

        self._connect()

    def _connect(self):
        try:
            self.conn = psycopg2.connect(self.database_url)
            self.conn.autocommit = True
            log.info("Connected to PostgreSQL database")
            self._init_schema()
        except Exception as e:
            log.error(f"Database connection failed: {e}")
            self.conn = None

    def _init_schema(self):
        """Create tables and indexes if they don't exist."""
        try:
            with self.conn.cursor() as cur:
                cur.execute(SCHEMA_SQL)
            log.info("Database schema initialized")
        except Exception as e:
            log.error(f"Schema initialization failed: {e}")

    def is_available(self) -> bool:
        return self.conn is not None

    def _ensure_connection(self):
        """Reconnect if the connection was lost."""
        if self.conn is None:
            return False
        try:
            with self.conn.cursor() as cur:
                cur.execute("SELECT 1")
            return True
        except Exception:
            log.warning("Database connection lost, reconnecting...")
            self._connect()
            return self.conn is not None

    def execute(self, query: str, params=None):
        """Execute a query and return the cursor (for INSERT/UPDATE)."""
        if not self._ensure_connection():
            return None
        try:
            with self.conn.cursor() as cur:
                cur.execute(query, params)
                return cur.rowcount
        except Exception as e:
            log.error(f"Database execute error: {e}")
            return None

    def fetch_all(self, query: str, params=None) -> list:
        """Execute a query and return all rows as dicts."""
        if not self._ensure_connection():
            return []
        try:
            with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(query, params)
                return cur.fetchall()
        except Exception as e:
            log.error(f"Database fetch error: {e}")
            return []

    def fetch_one(self, query: str, params=None):
        """Execute a query and return a single row as dict."""
        if not self._ensure_connection():
            return None
        try:
            with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(query, params)
                return cur.fetchone()
        except Exception as e:
            log.error(f"Database fetch_one error: {e}")
            return None

    def health_check(self) -> dict:
        if not self.is_available():
            return {"healthy": False, "reason": "Database not connected"}
        try:
            row = self.fetch_one("SELECT COUNT(*) as count FROM duration_records")
            return {
                "healthy": True,
                "total_records": row["count"] if row else 0,
            }
        except Exception as e:
            return {"healthy": False, "reason": str(e)}
