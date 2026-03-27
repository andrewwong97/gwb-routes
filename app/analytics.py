import hashlib
import logging
import time
from datetime import datetime, timezone
from typing import Optional

try:
    from .database import Database
except ImportError:
    from database import Database

log = logging.getLogger(__name__)


class AnalyticsStore:
    """Records and queries HTTP request analytics."""

    def __init__(self, db: Database):
        self.db = db

    @staticmethod
    def _hash_ip(ip: Optional[str]) -> Optional[str]:
        """One-way hash of IP for privacy. Returns None if no IP."""
        if not ip:
            return None
        return hashlib.sha256(ip.encode()).hexdigest()[:16]

    def log_request(
        self,
        method: str,
        path: str,
        query_string: Optional[str],
        status_code: int,
        duration_ms: int,
        ip: Optional[str] = None,
        user_agent: Optional[str] = None,
        referer: Optional[str] = None,
    ) -> bool:
        """Record a single request to the database."""
        if not self.db.is_available():
            return False

        result = self.db.execute(
            "INSERT INTO request_logs "
            "(method, path, query_string, status_code, duration_ms, ip_hash, user_agent, referer) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s, %s)",
            (method, path, query_string or None, status_code, duration_ms,
             self._hash_ip(ip), user_agent, referer),
        )
        return result is not None

    # ── Query methods ─────────────────────────────────────────────────

    def get_endpoint_stats(self, hours: int = 24) -> list:
        """Request count, avg duration, and error rate per endpoint."""
        return self.db.fetch_all(
            """
            SELECT
                path,
                COUNT(*)::INTEGER AS request_count,
                AVG(duration_ms)::INTEGER AS avg_duration_ms,
                COUNT(*) FILTER (WHERE status_code >= 400)::INTEGER AS error_count
            FROM request_logs
            WHERE timestamp > NOW() - INTERVAL '%s hours'
            GROUP BY path
            ORDER BY request_count DESC
            """,
            (hours,),
        )

    def get_requests_over_time(self, hours: int = 24, bucket_minutes: int = 60) -> list:
        """Request counts bucketed by time interval."""
        return self.db.fetch_all(
            """
            SELECT
                date_trunc('hour', timestamp)
                    + INTERVAL '1 minute' * (EXTRACT(minute FROM timestamp)::INT / %s * %s)
                    AS bucket,
                COUNT(*)::INTEGER AS request_count
            FROM request_logs
            WHERE timestamp > NOW() - INTERVAL '%s hours'
            GROUP BY bucket
            ORDER BY bucket
            """,
            (bucket_minutes, bucket_minutes, hours),
        )

    def get_recent_requests(self, limit: int = 50) -> list:
        """Most recent requests for a live-tail view."""
        return self.db.fetch_all(
            """
            SELECT timestamp, method, path, query_string,
                   status_code, duration_ms, user_agent
            FROM request_logs
            ORDER BY timestamp DESC
            LIMIT %s
            """,
            (limit,),
        )

    def get_unique_visitors(self, hours: int = 24) -> dict:
        """Count of unique IP hashes in a time window."""
        row = self.db.fetch_one(
            """
            SELECT
                COUNT(DISTINCT ip_hash)::INTEGER AS unique_visitors,
                COUNT(*)::INTEGER AS total_requests
            FROM request_logs
            WHERE timestamp > NOW() - INTERVAL '%s hours'
            """,
            (hours,),
        )
        return dict(row) if row else {"unique_visitors": 0, "total_requests": 0}
