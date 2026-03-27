import logging
from datetime import datetime, timezone
from typing import Optional

try:
    from .database import Database
    from .datamodels.location import Location
    from .response_models import RouteRecommendation
except ImportError:
    from database import Database
    from datamodels.location import Location
    from response_models import RouteRecommendation

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

    # -- Recommendation cache (Postgres-backed) --

    RECOMMENDATION_TTL_SECONDS = 180  # 3 minutes, matches Redis TTL

    def get_cached_recommendation(
        self, origin: str, destination: str
    ) -> Optional[RouteRecommendation]:
        """Return a cached recommendation if one exists and hasn't expired."""
        if not self.db.is_available():
            return None

        row = self.db.fetch_one(
            """
            SELECT * FROM recommendation_cache
            WHERE origin = %s AND destination = %s
              AND cached_at > NOW() - INTERVAL '%s seconds'
            """,
            (origin, destination, self.RECOMMENDATION_TTL_SECONDS),
        )
        if not row:
            return None

        log.info(f"Recommendation cache hit: {origin} → {destination}")
        return RouteRecommendation(
            recommended_level=row["recommended_level"],
            direction=row["direction"],
            upper_total=row["upper_total"],
            lower_total=row["lower_total"],
            upper_to_bridge=row["upper_to_bridge"],
            upper_bridge=row["upper_bridge"],
            upper_from_bridge=row["upper_from_bridge"],
            lower_to_bridge=row["lower_to_bridge"],
            lower_bridge=row["lower_bridge"],
            lower_from_bridge=row["lower_from_bridge"],
            time_saved=row["time_saved"],
        )

    def save_recommendation(
        self, origin: str, destination: str, rec: RouteRecommendation
    ) -> bool:
        """Upsert a recommendation into the cache."""
        if not self.db.is_available():
            return False

        result = self.db.execute(
            """
            INSERT INTO recommendation_cache
                (origin, destination, recommended_level, direction,
                 upper_total, lower_total,
                 upper_to_bridge, upper_bridge, upper_from_bridge,
                 lower_to_bridge, lower_bridge, lower_from_bridge,
                 time_saved, cached_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW())
            ON CONFLICT (origin, destination) DO UPDATE SET
                recommended_level = EXCLUDED.recommended_level,
                direction = EXCLUDED.direction,
                upper_total = EXCLUDED.upper_total,
                lower_total = EXCLUDED.lower_total,
                upper_to_bridge = EXCLUDED.upper_to_bridge,
                upper_bridge = EXCLUDED.upper_bridge,
                upper_from_bridge = EXCLUDED.upper_from_bridge,
                lower_to_bridge = EXCLUDED.lower_to_bridge,
                lower_bridge = EXCLUDED.lower_bridge,
                lower_from_bridge = EXCLUDED.lower_from_bridge,
                time_saved = EXCLUDED.time_saved,
                cached_at = NOW()
            """,
            (
                origin, destination, rec.recommended_level, rec.direction,
                rec.upper_total, rec.lower_total,
                rec.upper_to_bridge, rec.upper_bridge, rec.upper_from_bridge,
                rec.lower_to_bridge, rec.lower_bridge, rec.lower_from_bridge,
                rec.time_saved,
            ),
        )
        if result is not None:
            log.info(f"Cached recommendation: {origin} → {destination}")
        return result is not None

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
