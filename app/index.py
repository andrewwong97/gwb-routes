import requests

from fastapi import FastAPI
from fastapi.responses import PlainTextResponse

app = FastAPI()

# Copied from gwb_routes because relative imports broke and I'm lazy
def get_duration(api_key, origin, waypoint, dest="40.8640,-73.9336"):
    base_url = "https://maps.googleapis.com/maps/api/directions/json"
    params = {
        "origin": origin,
        "destination": dest,
        "waypoints": waypoint,
        "mode": "driving",
        "units": "imperial",
        "departure_time": "now",
        "traffic_model": "best_guess",
        "key": api_key,
    }
    resp = requests.get(base_url, params=params)
    data = resp.json()
    try:
        return data["routes"][0]["legs"][0]["duration_in_traffic"]["text"]
    except (KeyError, IndexError):
        return "N/A"

@app.get("/")
def read_root():
    api_key = os.getenv("GOOGLE_MAPS_API_KEY")
    origin = os.getenv("ORIGIN_LATLNG")
    upper_waypoint = "via:40.854144,-73.965899"
    lower_waypoint = "via:40.854603,-73.969891"

    upper_time = get_duration(api_key, origin, upper_waypoint)
    lower_time = get_duration(api_key, origin, lower_waypoint)

    return PlainTextResponse(f"From {origin}:\nUpper Level GWB: {upper_time}\nLower Level GWB: {lower_time}")

@app.get("/healthcheck")
def healthcheck():
    return {"status": "healthy"}

# This is important for Vercel
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)