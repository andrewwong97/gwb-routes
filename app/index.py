import os

from fastapi import FastAPI
from fastapi.responses import PlainTextResponse

from .gwb_routes import get_duration

app = FastAPI()

@app.get("/")
async def read_root():
    api_key = os.getenv("GOOGLE_MAPS_API_KEY")
    origin = os.getenv("ORIGIN_LATLNG")
    upper_waypoint = "via:40.854144,-73.965899"
    lower_waypoint = "via:40.854603,-73.969891"

    upper_time = get_duration(api_key, origin, upper_waypoint)
    lower_time = get_duration(api_key, origin, lower_waypoint)

    return PlainTextResponse(f"From NJ to NYC:\nUpper Level GWB: {upper_time}\nLower Level GWB: {lower_time}")

@app.get("/healthcheck")
def healthcheck():
    return {"status": "healthy"}

# This is important for Vercel
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)