# GWB Commute Operational Dashboard

This script fetches current driving times (with traffic) from your origin to the George Washington Bridge, comparing **Upper Level** and **Lower Level** routes.

<img width="865" height="760" alt="image" src="https://github.com/user-attachments/assets/daf4c757-cb6a-4e89-bb90-3ed577b1e553" />

## Getting an API key

Visit the following Google Cloud console and create a project with API access. Restrict the API key to only use Directions API.
https://console.cloud.google.com/welcome

Save the API key somewhere secure, you'll use it later.

# Development

This is deployed as a FastAPI web server, serving some URLs with an HTML template backed by same-origin fetches for data.

## Usage

Set up a python virtualenv and activate it:

1. `python -m venv venv`
2. `source venv/bin/activate`
3. `pip install -r requirements.txt`

**Commands**:

1. To run the fastapi server locally: `GOOGLE_MAPS_API_KEY=<the key> python app/index.py`
2. To just run the core lookup: `python app/run_inline.py <the key>`

# TidByt

Included in the root level directory is a Starlark .star file that can be compiled and rendered to a .webp executable for TidByt devices.
It's not complete, but it is a start. For more docs, check out: https://tidbyt.dev/docs/build/build-for-tidbyt

**November 2025**: As of late 2024, TidByt was acquired by Modal and developer support has declined greatly. That said, there is no plan to continue GWB routes support.

## How to use right now

Invoke https://gwb-routes.vercel.app via Siri shortcuts or as a browser favorite.

Or visit https://gwb-routes.vercel.app/dashboard.
