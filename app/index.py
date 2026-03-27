import os
import time
import logging
from typing import Optional

from fastapi import FastAPI, Request, Response, HTTPException, Query
from fastapi.responses import PlainTextResponse, FileResponse, HTMLResponse

from dotenv import load_dotenv

import sentry_sdk
from sentry_sdk import metrics

load_dotenv()

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)
try:
    # Try relative imports first (works in production/package context)
    from .api_client import ApiClient
    from .analytics import AnalyticsStore
    from .response_models import (
        GWBRoutes, RouteRecommendation,
        BestTimesResponse, TimeWindow,
        DailySummaryResponse, DailySummary,
        TimeSeriesResponse, DurationRecord, TrackedRoute,
    )
    log.info("Using relative imports")
except ImportError:
    # Fall back to absolute imports (works in local development)
    log.warning("Using absolute imports")
    from api_client import ApiClient
    from analytics import AnalyticsStore
    from response_models import (
        GWBRoutes, RouteRecommendation,
        BestTimesResponse, TimeWindow,
        DailySummaryResponse, DailySummary,
        TimeSeriesResponse, DurationRecord, TrackedRoute,
    )


try:
    sentry_sdk.init(
        dsn=os.getenv("SENTRY_DSN"),
        traces_sample_rate=1.0,
        profiles_sample_rate=1.0,
        _experiments={
            "enable_metrics": True
        }
    )
except Exception as e:
    log.error(f"Failed to initialize Sentry: {e}")

app = FastAPI()
api_client = ApiClient(os.getenv("GOOGLE_MAPS_API_KEY"))
if not api_client.api_key:
    log.error("GOOGLE_MAPS_API_KEY is not set")
    raise ValueError("GOOGLE_MAPS_API_KEY is not set")

analytics = AnalyticsStore(api_client.db)
log.info("Starting server...")


ANALYTICS_SKIP_PATHS = {"/healthcheck", "/favicon.ico", "/analytics"}


@app.middleware("http")
async def log_requests(request: Request, call_next):
    """Log every request to the analytics table."""
    # Skip logging for analytics/health endpoints to avoid feedback loops
    if any(request.url.path.startswith(p) for p in ANALYTICS_SKIP_PATHS):
        return await call_next(request)

    start = time.monotonic()
    response = await call_next(request)
    duration_ms = int((time.monotonic() - start) * 1000)

    try:
        analytics.log_request(
            method=request.method,
            path=request.url.path,
            query_string=str(request.url.query) if request.url.query else None,
            status_code=response.status_code,
            duration_ms=duration_ms,
            ip=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent"),
            referer=request.headers.get("referer"),
        )
    except Exception as e:
        log.warning(f"Failed to log analytics: {e}")

    return response

@app.get("/plaintext")
async def plaintext():
    response_text = api_client.get_times_as_text()
    metrics.count("plaintext.request", 1)
    return PlainTextResponse(
        response_text,
        headers={"Cache-Control": "public, max-age=180, s-maxage=180"}
    )

@app.get("/times", response_model=GWBRoutes)
async def read_times(response: Response):
    data = api_client.get_times_as_model()
    metrics.count("times.request", 1)
    response.headers["Cache-Control"] = "public, max-age=180, s-maxage=180"
    return data

@app.get("/recommend", response_model=RouteRecommendation)
async def recommend(
    origin: str = Query(..., description="Starting address or lat,lon"),
    destination: str = Query(..., description="Destination address or lat,lon"),
):
    try:
        data = api_client.get_route_recommendation(origin, destination)
        metrics.count("recommend.request", 1)
        return data
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        log.error(f"Error getting route recommendation: {e}")
        raise HTTPException(status_code=500, detail="Error calculating route recommendation")


@app.get("/places/autocomplete")
async def places_autocomplete(input: str = Query(..., min_length=2)):
    results = api_client.places_autocomplete(input)
    return results


@app.get("/healthcheck")
def healthcheck():
    return {"status": "healthy"}


@app.get("/", response_class=HTMLResponse)
@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard(response: Response):
    """Serve the dashboard HTML page"""
    try:
        with open("static/index.html", "r", encoding="utf-8") as f:
            html_content = f.read()
        # Replace localhost:8000 with relative URLs for production
        html_content = html_content.replace('"http://localhost:8000"', '""')
        # Cache for 10 minutes - longer than data cache but not too long for UI updates
        response.headers["Cache-Control"] = "public, max-age=600, s-maxage=600"
        metrics.count("dashboard.request", 1)
        return HTMLResponse(content=html_content)
    except FileNotFoundError:
        return HTMLResponse(content="<h1>Dashboard not found</h1>", status_code=404)

@app.get("/favicon.ico", include_in_schema=False)
async def favicon():
    return FileResponse(os.path.join("static", "favicon.png"), media_type="image/png")


# ── History / Analytics endpoints ──────────────────────────────────────

@app.get("/history/routes", response_model=list[TrackedRoute])
async def list_tracked_routes():
    """List all routes that have historical data."""
    rows = api_client.history.get_routes()
    return [
        TrackedRoute(
            name=r["name"],
            id=r["id"],
            record_count=r["record_count"],
            first_recorded=str(r["first_recorded"]) if r["first_recorded"] else None,
            last_recorded=str(r["last_recorded"]) if r["last_recorded"] else None,
        )
        for r in rows
    ]


@app.get("/history/{route_name}/best-times", response_model=BestTimesResponse)
async def best_times(
    route_name: str,
    day_of_week: Optional[int] = Query(None, ge=0, le=6, description="0=Monday, 6=Sunday"),
):
    """Get the best times to travel for a route, ranked by average duration.

    Returns 15-minute windows sorted from fastest to slowest.
    Optionally filter by day of week.
    """
    windows = api_client.history.get_best_times(route_name, day_of_week)
    return BestTimesResponse(
        route_name=route_name,
        day_of_week=day_of_week,
        windows=[TimeWindow(**w) for w in windows],
    )


@app.get("/history/{route_name}/daily", response_model=DailySummaryResponse)
async def daily_summary(route_name: str):
    """Get average duration by day of week for a route."""
    days = api_client.history.get_daily_summary(route_name)
    return DailySummaryResponse(
        route_name=route_name,
        days=[DailySummary(**d) for d in days],
    )


@app.get("/history/{route_name}/series", response_model=TimeSeriesResponse)
async def time_series(
    route_name: str,
    limit: int = Query(500, ge=1, le=5000, description="Max records to return"),
):
    """Get raw historical duration records for a route (most recent first)."""
    records = api_client.history.get_time_series(route_name, limit)
    return TimeSeriesResponse(
        route_name=route_name,
        records=[
            DurationRecord(
                duration_seconds=r["duration_seconds"],
                captured_at=str(r["captured_at"]),
                day_of_week=r["day_of_week"],
                hour_of_day=r["hour_of_day"],
                minute_bucket=r["minute_bucket"],
            )
            for r in records
        ],
    )


@app.get("/history/db-health")
async def db_health():
    """Check database connectivity and record count."""
    return api_client.db.health_check()


# ── User Analytics endpoints ─────────────────────────────────────────

@app.get("/analytics/endpoints")
async def analytics_endpoints(
    hours: int = Query(24, ge=1, le=720, description="Lookback window in hours"),
):
    """Request count, avg latency, and error count per endpoint."""
    return analytics.get_endpoint_stats(hours)


@app.get("/analytics/traffic")
async def analytics_traffic(
    hours: int = Query(24, ge=1, le=720, description="Lookback window in hours"),
    bucket_minutes: int = Query(60, ge=1, le=1440, description="Bucket size in minutes"),
):
    """Request counts bucketed over time."""
    return analytics.get_requests_over_time(hours, bucket_minutes)


@app.get("/analytics/visitors")
async def analytics_visitors(
    hours: int = Query(24, ge=1, le=720, description="Lookback window in hours"),
):
    """Unique visitor and total request counts."""
    return analytics.get_unique_visitors(hours)


@app.get("/analytics/recent")
async def analytics_recent(
    limit: int = Query(50, ge=1, le=500, description="Number of recent requests"),
):
    """Live tail of the most recent requests."""
    rows = analytics.get_recent_requests(limit)
    for r in rows:
        if r.get("timestamp"):
            r["timestamp"] = str(r["timestamp"])
    return rows


# This is important for Vercel
if __name__ == "__main__":
    import uvicorn
    metrics.count("server.start", 1)
    uvicorn.run(app, host="0.0.0.0", port=8000)