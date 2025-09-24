import os

from fastapi import FastAPI, Response
from fastapi.responses import PlainTextResponse
from fastapi.responses import FileResponse
import os

from .gwb_routes import get_final_text

app = FastAPI()

@app.get("/")
async def read_root():
    api_key = os.getenv("GOOGLE_MAPS_API_KEY")
    
    response_text = get_final_text(api_key)

    return PlainTextResponse(
        response_text,
        headers={"Cache-Control": "public, max-age=180, s-maxage=180"}
    )

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