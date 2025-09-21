#!/usr/bin/env python3

import sys
import requests

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

def main():
    if len(sys.argv) < 3:
        print(f"Usage: {sys.argv[0]} <GOOGLE_MAPS_API_KEY> <ORIGIN_LAT,LNG>")
        sys.exit(1)

    api_key = sys.argv[1]
    origin = sys.argv[2]

    upper_waypoint = "via:40.854144,-73.965899"
    lower_waypoint = "via:40.854603,-73.969891"

    upper_time = get_duration(api_key, origin, upper_waypoint)
    lower_time = get_duration(api_key, origin, lower_waypoint)

    print(f"From {origin}:")
    print(f"  Upper Level GWB: {upper_time}")
    print(f"  Lower Level GWB: {lower_time}")

if __name__ == "__main__":
    main()

