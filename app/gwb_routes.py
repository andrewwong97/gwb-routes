#!/usr/bin/env python3

import sys
import requests

def get_duration(api_key, origin, dest):
    base_url = "https://maps.googleapis.com/maps/api/directions/json"
    params = {
        "origin": origin,
        "destination": dest,
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

def main():
    if len(sys.argv) < 2:
        print(f"Usage: {sys.argv[0]} <GOOGLE_MAPS_API_KEY>")
        sys.exit(1)

    api_key = sys.argv[1]
    
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

    print("NJ to NYC:")
    print(f"  Upper Level GWB: {upper_time_to_nyc}")
    print(f"  Lower Level GWB: {lower_time_to_nyc}")
    print()
    print("NYC to NJ:")
    print(f"  Upper Level GWB: {upper_time_to_nj}")
    print(f"  Lower Level GWB: {lower_time_to_nj}")

if __name__ == "__main__":
    main()

