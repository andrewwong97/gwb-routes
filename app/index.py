import os

from fastapi import FastAPI, Response
from fastapi.responses import PlainTextResponse
from fastapi.responses import FileResponse

from api_client import ApiClient
from models import GWBRoutes

app = FastAPI()
api_client = ApiClient(os.getenv("GOOGLE_MAPS_API_KEY"))

@app.get("/")
async def read_root():
    response_text = api_client.get_times_as_text()

    return PlainTextResponse(
        response_text,
        headers={"Cache-Control": "public, max-age=180, s-maxage=180"}
    )

@app.get("/times", response_model=GWBRoutes)
async def read_times():
    return api_client.get_times_as_model()

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