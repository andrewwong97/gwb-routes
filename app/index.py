import os
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
    from .response_models import (
        GWBRoutes, RouteRecommendation,
        BestTimesResponse, TimeWindow,
        DailySummaryResponse, DailySummary,
        TimeSeriesResponse, DurationRecord, TrackedRoute,
        HourlyProfileResponse, HourlyBucket,
        HeatmapResponse, HeatmapCell,
        PeakComparisonResponse, PeriodStats,
        TrendResponse, TrendPeriod,
        RouteComparisonResponse, RouteComparisonEntry,
    )
    log.info("Using relative imports")
except ImportError:
    # Fall back to absolute imports (works in local development)
    log.warning("Using absolute imports")
    from api_client import ApiClient
    from response_models import (
        GWBRoutes, RouteRecommendation,
        BestTimesResponse, TimeWindow,
        DailySummaryResponse, DailySummary,
        TimeSeriesResponse, DurationRecord, TrackedRoute,
        HourlyProfileResponse, HourlyBucket,
        HeatmapResponse, HeatmapCell,
        PeakComparisonResponse, PeriodStats,
        TrendResponse, TrendPeriod,
        RouteComparisonResponse, RouteComparisonEntry,
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

log.info("Starting server...")

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
        # Inject Microsoft Clarity tracking if configured
        clarity_id = os.environ.get("CLARITY_PROJECT_ID", "")
        if clarity_id:
            clarity_script = (
                '<script type="text/javascript">'
                "(function(c,l,a,r,i,t,y){"
                "c[a]=c[a]||function(){(c[a].q=c[a].q||[]).push(arguments)};"
                "t=l.createElement(r);t.async=1;t.src=\"https://www.clarity.ms/tag/\"+i;"
                "y=l.getElementsByTagName(r)[0];y.parentNode.insertBefore(t,y);"
                f"}})(window, document, \"clarity\", \"script\", \"{clarity_id}\");"
                "</script>"
            )
            html_content = html_content.replace("<!-- __CLARITY_SCRIPT__ -->", clarity_script)
        else:
            html_content = html_content.replace("<!-- __CLARITY_SCRIPT__ -->", "")
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


# ── Insights endpoints ────────────────────────────────────────────────

@app.get("/history/{route_name}/hourly", response_model=HourlyProfileResponse)
async def hourly_profile(
    route_name: str,
    filter: str = Query("all", pattern="^(all|weekday|weekend)$",
                         description="all, weekday (Mon-Fri), or weekend (Sat-Sun)"),
):
    """Average duration by hour of day, optionally filtered by weekday/weekend."""
    hours = api_client.history.get_hourly_profile(
        route_name,
        weekday_only=(filter == "weekday"),
        weekend_only=(filter == "weekend"),
    )
    return HourlyProfileResponse(
        route_name=route_name,
        filter=filter,
        hours=[HourlyBucket(**h) for h in hours],
    )


@app.get("/history/{route_name}/heatmap", response_model=HeatmapResponse)
async def heatmap(route_name: str):
    """Average duration by day-of-week and hour (for heatmap visualization)."""
    cells = api_client.history.get_heatmap(route_name)
    return HeatmapResponse(
        route_name=route_name,
        cells=[HeatmapCell(**c) for c in cells],
    )


@app.get("/history/{route_name}/peak", response_model=PeakComparisonResponse)
async def peak_comparison(route_name: str):
    """Compare rush-hour (7-9 AM, 5-7 PM) vs off-peak durations."""
    data = api_client.history.get_peak_comparison(route_name)
    return PeakComparisonResponse(
        route_name=route_name,
        peak=PeriodStats(**data["peak"]) if "peak" in data else None,
        off_peak=PeriodStats(**data["off_peak"]) if "off_peak" in data else None,
    )


@app.get("/history/{route_name}/trend", response_model=TrendResponse)
async def trend(
    route_name: str,
    recent_days: int = Query(7, ge=1, le=30, description="Recent window in days"),
    baseline_days: int = Query(30, ge=7, le=90, description="Baseline window in days"),
):
    """Compare recent average duration vs older baseline to detect trends."""
    data = api_client.history.get_trend(route_name, recent_days, baseline_days)
    return TrendResponse(
        route_name=route_name,
        recent_days=data.get("recent_days", recent_days),
        baseline_days=data.get("baseline_days", baseline_days),
        recent=TrendPeriod(**data["recent"]) if "recent" in data else None,
        baseline=TrendPeriod(**data["baseline"]) if "baseline" in data else None,
        change_pct=data.get("change_pct"),
    )


@app.get("/history/compare/{direction}", response_model=RouteComparisonResponse)
async def route_comparison(direction: str):
    """Compare upper vs lower level for a direction based on historical averages."""
    if direction not in ("nj_to_nyc", "nyc_to_nj"):
        raise HTTPException(status_code=400, detail="direction must be nj_to_nyc or nyc_to_nj")
    rows = api_client.history.get_route_comparison(direction)
    return RouteComparisonResponse(
        direction=direction,
        routes=[RouteComparisonEntry(**r) for r in rows],
    )


@app.get("/history/db-health")
async def db_health():
    """Check database connectivity and record count."""
    return api_client.db.health_check()


# ── Cron endpoint ─────────────────────────────────────────────────────

@app.get("/cron/collect")
async def cron_collect(request: Request):
    """Fetch all 4 route durations and record them to the database.

    Called daily by Vercel Cron (hobby tier). Protected by CRON_SECRET.
    Clears the route cache first so we always get fresh Google Maps data.
    """
    # Vercel Cron sends an Authorization header with the CRON_SECRET
    cron_secret = os.getenv("CRON_SECRET")
    if cron_secret:
        auth = request.headers.get("authorization")
        if auth != f"Bearer {cron_secret}":
            raise HTTPException(status_code=401, detail="Unauthorized")

    try:
        # Clear cached route durations so we get fresh data from Google Maps
        api_client.clear_cache("route:*")

        # get_times_as_model calls get_duration for all 4 routes,
        # which records each duration to the database automatically
        data = api_client.get_times_as_model()
        log.info(f"Cron collect complete: upper_nyc={data.upper_level_nyc}, "
                 f"lower_nyc={data.lower_level_nyc}, "
                 f"upper_nj={data.upper_level_nj}, "
                 f"lower_nj={data.lower_level_nj}")
        return {
            "status": "ok",
            "recorded": {
                "upper_nj_to_nyc": data.upper_level_nyc,
                "lower_nj_to_nyc": data.lower_level_nyc,
                "upper_nyc_to_nj": data.upper_level_nj,
                "lower_nyc_to_nj": data.lower_level_nj,
            },
        }
    except Exception as e:
        log.error(f"Cron collect failed: {e}")
        raise HTTPException(status_code=500, detail=f"Collection failed: {e}")


# This is important for Vercel
if __name__ == "__main__":
    import uvicorn
    metrics.count("server.start", 1)
    uvicorn.run(app, host="0.0.0.0", port=8000)