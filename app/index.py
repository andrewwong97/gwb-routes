import os
import logging

from fastapi import FastAPI, Response, HTTPException, Query
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
    from .response_models import GWBRoutes, RouteRecommendation
    log.info("Using relative imports")
except ImportError:
    # Fall back to absolute imports (works in local development)
    log.warning("Using absolute imports")
    from api_client import ApiClient
    from response_models import GWBRoutes, RouteRecommendation


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

@app.get("/autocomplete")
async def autocomplete(input: str = Query(..., min_length=1)):
    """Proxy Google Places Autocomplete so the API key never reaches the browser."""
    import requests as _requests
    resp = _requests.get(
        "https://maps.googleapis.com/maps/api/place/autocomplete/json",
        params={
            "input": input,
            "types": "geocode",
            "components": "country:us",
            "key": os.getenv("GOOGLE_MAPS_API_KEY"),
        },
        timeout=5,
    )
    data = resp.json()
    predictions = [p["description"] for p in data.get("predictions", [])]
    return {"predictions": predictions}


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

# This is important for Vercel
if __name__ == "__main__":
    import uvicorn
    metrics.count("server.start", 1)
    uvicorn.run(app, host="0.0.0.0", port=8000)