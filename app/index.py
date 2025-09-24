import os

from fastapi import FastAPI
from fastapi.responses import PlainTextResponse
from fastapi.responses import FileResponse
import os

from .gwb_routes import get_duration

app = FastAPI()

@app.get("/")
async def read_root():
    api_key = os.getenv("GOOGLE_MAPS_API_KEY")
    
    # Hardcoded locations
    nj_location = "40.7589,-74.0758"    # Default NJ location (Fort Lee area)
    nyc_location = "40.8640,-73.9336"   # NYC Bus Terminal
    
    # GWB ramp coordinates as direct origins/destinations
    gwb_upper_nj_side = "40.854144,-73.965899"      # Upper level NJ side
    gwb_lower_nj_side = "40.854603,-73.969891"      # Lower level NJ side
    gwb_upper_nyc_side = "40.847201175544896,-73.94314583135964"  # Upper level NYC side
    gwb_lower_nyc_side = "40.84736948200483,-73.94270802155232"   # Lower level NYC side

    # NJ to NYC direction (GWB NJ-side ramps → NYC location)
    upper_time_to_nyc = get_duration(api_key, gwb_upper_nj_side, nyc_location)
    lower_time_to_nyc = get_duration(api_key, gwb_lower_nj_side, nyc_location)
    
    # NYC to NJ direction (GWB NYC-side ramps → NJ location)
    upper_time_to_nj = get_duration(api_key, gwb_upper_nyc_side, nj_location)
    lower_time_to_nj = get_duration(api_key, gwb_lower_nyc_side, nj_location)

    response_text = f"""NJ to NYC:
Upper Level GWB: {upper_time_to_nyc}
Lower Level GWB: {lower_time_to_nyc}

NYC to NJ:
Upper Level GWB: {upper_time_to_nj}
Lower Level GWB: {lower_time_to_nj}"""

    return PlainTextResponse(response_text)

@app.get("/healthcheck")
def healthcheck():
    return {"status": "healthy"}



@app.get("/favicon.ico", include_in_schema=False)
async def favicon():
    return FileResponse(os.path.join("static", "favicon.svg"), media_type="image/svg+xml")

# This is important for Vercel
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)