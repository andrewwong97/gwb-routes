# GWB Commute Time Script

This script fetches current driving times (with traffic) from your origin to the George Washington Bridge, comparing **Upper Level** and **Lower Level** routes.

## Getting an API key
Visit the following Google Cloud console and create a project with API access. Restrict the API key to only use Directions API.
https://console.cloud.google.com/welcome

Save the API key somewhere secure, you'll use it later.

## Usage

Set up a python virtualenv and activate it:
1. `python -m venv venv`
2. `source venv/bin/activate`
3. `pip install -r requirements.txt`

Make sure to `chmod +x gwb_routes.sh` to make it executable.
```bash
./gwb_routes.sh <Google Maps Directions API Key> "<LAT>, <LNG>"
```


## TidByt
Included in the root level directory is a Starlark .star file that can be compiled and rendered to a .webp executable for TidByt devices.
It's not complete, but it is a start. For more docs, check out: https://tidbyt.dev/docs/build/build-for-tidbyt

## How to use right now
Invoke https://gwb-routes.vercel.app via Siri shortcuts or as a browser favorite.

