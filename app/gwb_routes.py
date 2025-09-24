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
    
def get_final_text(api_key):
    # Hardcoded destinations
    fletcher_ave = "40.85923408136495, -73.97199910595126"    # Fletcher Ave
    gwb_bus_terminal = "40.84915583675182, -73.93987065819441"   # GWB Bus Terminal
    
    # GWB ramp coordinates as direct origins/destinations
    gwb_upper_nj_side = "40.853575616805294, -73.96277775559088"      # Upper level NJ side
    gwb_lower_nj_side = "40.853386143945826, -73.96296693613093"      # Lower level NJ side
    gwb_upper_nyc_side = "40.8470196232696, -73.94314593858371"       # Upper level NYC side
    gwb_lower_nyc_side = "40.847470731893516, -73.94267562542835"     # Lower level NYC side

    # NJ to NYC direction (GWB NJ-side ramps → NYC location)
    upper_time_to_nyc = get_duration(api_key, gwb_upper_nj_side, gwb_bus_terminal)
    lower_time_to_nyc = get_duration(api_key, gwb_lower_nj_side, gwb_bus_terminal)
    
    # NYC to NJ direction (GWB NYC-side ramps → NJ location)
    upper_time_to_nj = get_duration(api_key, gwb_upper_nyc_side, fletcher_ave)
    lower_time_to_nj = get_duration(api_key, gwb_lower_nyc_side, fletcher_ave)

    response_text = f"""
----------------------------------------
NJ to NYC:
----------------------------------------
Upper Level GWB: {upper_time_to_nyc}
Lower Level GWB: {lower_time_to_nyc}

----------------------------------------
NYC to NJ:
----------------------------------------
Upper Level GWB: {upper_time_to_nj}
Lower Level GWB: {lower_time_to_nj}
    """
    return response_text

def main():
    if len(sys.argv) < 2:
        print(f"Usage: {sys.argv[0]} <GOOGLE_MAPS_API_KEY>")
        sys.exit(1)

    api_key = sys.argv[1]
    
    response_text = get_final_text(api_key)

    print(response_text)


if __name__ == "__main__":
    main()

