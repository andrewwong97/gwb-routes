import logging
from datetime import datetime, timezone
from typing import Optional

try:
    from .database import Database
    from .datamodels.location import Location
except ImportError:
    from database import Database
    from datamodels.location import Location

log = logging.getLogger(__name__)


class HistoryStore:
    """Records and queries historical route duration data."""

    def __init__(self, db: Database):
        self.db = db

    def _get_or_create_location(self, loc: Location) -> Optional[int]:
        """Upsert a location and return its id."""
        if not self.db.is_available():
            return None

        row = self.db.fetch_one(
            "SELECT id FROM locations WHERE lat = %s AND lon = %s",
            (loc.lat, loc.lon),
        )
        if row:
            return row["id"]

        self.db.execute(
            "INSERT INTO locations (lat, lon, name) VALUES (%s, %s, %s) "
            "ON CONFLICT (lat, lon) DO NOTHING",
            (loc.lat, loc.lon, loc.get_name()),
        )
        row = self.db.fetch_one(
            "SELECT id FROM locations WHERE lat = %s AND lon = %s",
            (loc.lat, loc.lon),
        )
        return row["id"] if row else None

    def _get_or_create_route(self, name: str, src: Location, dst: Location) -> Optional[int]:
        """Upsert a route and return its id."""
        if not self.db.is_available():
            return None

        row = self.db.fetch_one("SELECT id FROM routes WHERE name = %s", (name,))
        if row:
            return row["id"]

        src_id = self._get_or_create_location(src)
        dst_id = self._get_or_create_location(dst)
        if src_id is None or dst_id is None:
            return None

        self.db.execute(
            "INSERT INTO routes (name, src_id, dst_id) VALUES (%s, %s, %s) "
            "ON CONFLICT (name) DO NOTHING",
            (name, src_id, dst_id),
        )
        row = self.db.fetch_one("SELECT id FROM routes WHERE name = %s", (name,))
        return row["id"] if row else None

    def record_duration(
        self,
        route_name: str,
        src: Location,
        dst: Location,
        duration_seconds: int,
        captured_at: Optional[datetime] = None,
    ) -> bool:
        """Record a duration observation for a route."""
        if not self.db.is_available():
            return False

        route_id = self._get_or_create_route(route_name, src, dst)
        if route_id is None:
            return False

        if captured_at is None:
            captured_at = datetime.now(timezone.utc)

        day_of_week = captured_at.weekday()  # 0=Monday, 6=Sunday
        hour_of_day = captured_at.hour
        minute_bucket = (captured_at.minute // 15) * 15  # 0, 15, 30, 45

        result = self.db.execute(
            "INSERT INTO duration_records "
            "(route_id, duration_seconds, captured_at, day_of_week, hour_of_day, minute_bucket) "
            "VALUES (%s, %s, %s, %s, %s, %s)",
            (route_id, duration_seconds, captured_at, day_of_week, hour_of_day, minute_bucket),
        )
        if result:
            log.info(f"Recorded duration: {route_name} = {duration_seconds}s at {captured_at}")
        return result is not None

    def get_best_times(self, route_name: str, day_of_week: Optional[int] = None) -> list:
        """Get average durations by time window, optionally filtered by day of week.

        Returns rows sorted by average duration (best times first):
            [{day_of_week, hour_of_day, minute_bucket, avg_seconds, median_seconds, sample_count}, ...]
        """
        if not self.db.is_available():
            return []

        if day_of_week is not None:
            rows = self.db.fetch_all(
                """
                SELECT
                    dr.day_of_week,
                    dr.hour_of_day,
                    dr.minute_bucket,
                    AVG(dr.duration_seconds)::INTEGER AS avg_seconds,
                    PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY dr.duration_seconds)::INTEGER AS median_seconds,
                    COUNT(*)::INTEGER AS sample_count
                FROM duration_records dr
                JOIN routes r ON r.id = dr.route_id
                WHERE r.name = %s AND dr.day_of_week = %s
                GROUP BY dr.day_of_week, dr.hour_of_day, dr.minute_bucket
                HAVING COUNT(*) >= 1
                ORDER BY avg_seconds ASC
                """,
                (route_name, day_of_week),
            )
        else:
            rows = self.db.fetch_all(
                """
                SELECT
                    dr.day_of_week,
                    dr.hour_of_day,
                    dr.minute_bucket,
                    AVG(dr.duration_seconds)::INTEGER AS avg_seconds,
                    PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY dr.duration_seconds)::INTEGER AS median_seconds,
                    COUNT(*)::INTEGER AS sample_count
                FROM duration_records dr
                JOIN routes r ON r.id = dr.route_id
                WHERE r.name = %s
                GROUP BY dr.day_of_week, dr.hour_of_day, dr.minute_bucket
                HAVING COUNT(*) >= 1
                ORDER BY avg_seconds ASC
                """,
                (route_name,),
            )

        return [dict(r) for r in rows]

    def get_time_series(self, route_name: str, limit: int = 500) -> list:
        """Get raw duration records for a route, sorted by captured_at desc.

        Returns: [{duration_seconds, captured_at, day_of_week, hour_of_day}, ...]
        """
        if not self.db.is_available():
            return []

        rows = self.db.fetch_all(
            """
            SELECT
                dr.duration_seconds,
                dr.captured_at,
                dr.day_of_week,
                dr.hour_of_day,
                dr.minute_bucket
            FROM duration_records dr
            JOIN routes r ON r.id = dr.route_id
            WHERE r.name = %s
            ORDER BY dr.captured_at DESC
            LIMIT %s
            """,
            (route_name, limit),
        )
        return [dict(r) for r in rows]

    def get_routes(self) -> list:
        """List all tracked routes."""
        if not self.db.is_available():
            return []

        rows = self.db.fetch_all(
            """
            SELECT r.name, r.id,
                   COUNT(dr.id)::INTEGER AS record_count,
                   MIN(dr.captured_at) AS first_recorded,
                   MAX(dr.captured_at) AS last_recorded
            FROM routes r
            LEFT JOIN duration_records dr ON dr.route_id = r.id
            GROUP BY r.id, r.name
            ORDER BY r.name
            """
        )
        return [dict(r) for r in rows]

    def get_hourly_profile(self, route_name: str, weekday_only: bool = False,
                           weekend_only: bool = False) -> list:
        """Get average duration by hour of day, optionally filtered by weekday/weekend.

        Returns: [{hour_of_day, avg_seconds, median_seconds, min_seconds, max_seconds, sample_count}, ...]
        """
        if not self.db.is_available():
            return []

        where_extra = ""
        if weekday_only:
            where_extra = " AND dr.day_of_week < 5"
        elif weekend_only:
            where_extra = " AND dr.day_of_week >= 5"

        rows = self.db.fetch_all(
            f"""
            SELECT
                dr.hour_of_day,
                AVG(dr.duration_seconds)::INTEGER AS avg_seconds,
                PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY dr.duration_seconds)::INTEGER AS median_seconds,
                MIN(dr.duration_seconds) AS min_seconds,
                MAX(dr.duration_seconds) AS max_seconds,
                COUNT(*)::INTEGER AS sample_count
            FROM duration_records dr
            JOIN routes r ON r.id = dr.route_id
            WHERE r.name = %s{where_extra}
            GROUP BY dr.hour_of_day
            ORDER BY dr.hour_of_day
            """,
            (route_name,),
        )
        return [dict(r) for r in rows]

    def get_heatmap(self, route_name: str) -> list:
        """Get avg duration by day_of_week and hour_of_day (heatmap matrix).

        Returns: [{day_of_week, hour_of_day, avg_seconds, sample_count}, ...]
        """
        if not self.db.is_available():
            return []

        rows = self.db.fetch_all(
            """
            SELECT
                dr.day_of_week,
                dr.hour_of_day,
                AVG(dr.duration_seconds)::INTEGER AS avg_seconds,
                COUNT(*)::INTEGER AS sample_count
            FROM duration_records dr
            JOIN routes r ON r.id = dr.route_id
            WHERE r.name = %s
            GROUP BY dr.day_of_week, dr.hour_of_day
            ORDER BY dr.day_of_week, dr.hour_of_day
            """,
            (route_name,),
        )
        return [dict(r) for r in rows]

    def get_peak_comparison(self, route_name: str) -> dict:
        """Compare rush-hour (7-9, 17-19) vs off-peak durations.

        Returns: {peak: {avg, median, sample_count}, off_peak: {avg, median, sample_count}}
        """
        if not self.db.is_available():
            return {}

        rows = self.db.fetch_all(
            """
            SELECT
                CASE WHEN dr.hour_of_day IN (7, 8, 17, 18) THEN 'peak' ELSE 'off_peak' END AS period,
                AVG(dr.duration_seconds)::INTEGER AS avg_seconds,
                PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY dr.duration_seconds)::INTEGER AS median_seconds,
                COUNT(*)::INTEGER AS sample_count
            FROM duration_records dr
            JOIN routes r ON r.id = dr.route_id
            WHERE r.name = %s
            GROUP BY period
            """,
            (route_name,),
        )
        result = {}
        for r in rows:
            result[r["period"]] = {
                "avg_seconds": r["avg_seconds"],
                "median_seconds": r["median_seconds"],
                "sample_count": r["sample_count"],
            }
        return result

    def get_trend(self, route_name: str, recent_days: int = 7, baseline_days: int = 30) -> dict:
        """Compare recent avg duration vs older baseline.

        Returns: {recent: {avg, sample_count, period_days}, baseline: {avg, sample_count, period_days}, change_pct}
        """
        if not self.db.is_available():
            return {}

        rows = self.db.fetch_all(
            """
            SELECT
                CASE
                    WHEN dr.captured_at >= NOW() - INTERVAL '%s days' THEN 'recent'
                    WHEN dr.captured_at >= NOW() - INTERVAL '%s days' THEN 'baseline'
                END AS period,
                AVG(dr.duration_seconds)::INTEGER AS avg_seconds,
                COUNT(*)::INTEGER AS sample_count
            FROM duration_records dr
            JOIN routes r ON r.id = dr.route_id
            WHERE r.name = %s
              AND dr.captured_at >= NOW() - INTERVAL '%s days'
            GROUP BY period
            """,
            (recent_days, baseline_days, route_name, baseline_days),
        )

        result = {"recent_days": recent_days, "baseline_days": baseline_days}
        for r in rows:
            if r["period"]:
                result[r["period"]] = {
                    "avg_seconds": r["avg_seconds"],
                    "sample_count": r["sample_count"],
                }

        if "recent" in result and "baseline" in result and result["baseline"]["avg_seconds"]:
            recent_avg = result["recent"]["avg_seconds"]
            baseline_avg = result["baseline"]["avg_seconds"]
            result["change_pct"] = round((recent_avg - baseline_avg) / baseline_avg * 100, 1)

        return result

    def get_route_comparison(self, direction: str) -> list:
        """Compare upper vs lower level for a given direction (nj_to_nyc or nyc_to_nj).

        Returns: [{route_name, avg_seconds, median_seconds, sample_count}, ...]
        """
        if not self.db.is_available():
            return []

        rows = self.db.fetch_all(
            """
            SELECT
                r.name AS route_name,
                AVG(dr.duration_seconds)::INTEGER AS avg_seconds,
                PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY dr.duration_seconds)::INTEGER AS median_seconds,
                MIN(dr.duration_seconds) AS min_seconds,
                MAX(dr.duration_seconds) AS max_seconds,
                COUNT(*)::INTEGER AS sample_count
            FROM duration_records dr
            JOIN routes r ON r.id = dr.route_id
            WHERE r.name LIKE %s
            GROUP BY r.name
            ORDER BY avg_seconds ASC
            """,
            (f"%{direction}",),
        )
        return [dict(r) for r in rows]

    def get_daily_summary(self, route_name: str) -> list:
        """Get average duration by day of week for a route.

        Returns: [{day_of_week, avg_seconds, median_seconds, sample_count}, ...]
        """
        if not self.db.is_available():
            return []

        rows = self.db.fetch_all(
            """
            SELECT
                dr.day_of_week,
                AVG(dr.duration_seconds)::INTEGER AS avg_seconds,
                PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY dr.duration_seconds)::INTEGER AS median_seconds,
                MIN(dr.duration_seconds) AS min_seconds,
                MAX(dr.duration_seconds) AS max_seconds,
                COUNT(*)::INTEGER AS sample_count
            FROM duration_records dr
            JOIN routes r ON r.id = dr.route_id
            WHERE r.name = %s
            GROUP BY dr.day_of_week
            ORDER BY dr.day_of_week
            """,
            (route_name,),
        )
        return [dict(r) for r in rows]
