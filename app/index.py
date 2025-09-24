import os

from fastapi import FastAPI, Response
from fastapi.responses import PlainTextResponse, FileResponse, HTMLResponse

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
async def read_times(response: Response):
    data = api_client.get_times_as_model()
    response.headers["Cache-Control"] = "public, max-age=180, s-maxage=180"
    return data

@app.get("/healthcheck")
def healthcheck():
    return {"status": "healthy"}


@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard(response: Response):
    """Serve the dashboard HTML page"""
    try:
        with open("index.html", "r", encoding="utf-8") as f:
            html_content = f.read()
        # Replace localhost:8000 with relative URLs for production
        html_content = html_content.replace('"http://localhost:8000"', '""')
        # Cache for 10 minutes - longer than data cache but not too long for UI updates
        response.headers["Cache-Control"] = "public, max-age=600, s-maxage=600"
        return HTMLResponse(content=html_content)
    except FileNotFoundError:
        return HTMLResponse(content="<h1>Dashboard not found</h1>", status_code=404)

@app.get("/favicon.ico", include_in_schema=False)
async def favicon():
    return FileResponse(os.path.join("static", "favicon.svg"), media_type="image/svg+xml")

# This is important for Vercel
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)