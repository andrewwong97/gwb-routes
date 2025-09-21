#!/usr/bin/env bash

API_KEY=$1
ORIGIN=$2

if [ -z "$API_KEY" ] || [ -z "$ORIGIN" ]; then
  echo "Usage: $0 <GOOGLE_MAPS_API_KEY> <ORIGIN_LAT,LNG>"
  exit 1
fi

BASE_URL="https://maps.googleapis.com/maps/api/directions/json"
DEST="40.8640,-73.9336"

# Upper level waypoint
UPPER_WAYPOINT="via:40.854144,-73.965899"
# Lower level waypoint
LOWER_WAYPOINT="via:40.854603,-73.969891"

upper_time=$(curl -s "$BASE_URL?origin=$ORIGIN&destination=$DEST&waypoints=$UPPER_WAYPOINT&mode=driving&units=imperial&departure_time=now&traffic_model=best_guess&key=$API_KEY" \
  | jq -r '.routes[0].legs[0].duration_in_traffic.text')

lower_time=$(curl -s "$BASE_URL?origin=$ORIGIN&destination=$DEST&waypoints=$LOWER_WAYPOINT&mode=driving&units=imperial&departure_time=now&traffic_model=best_guess&key=$API_KEY" \
  | jq -r '.routes[0].legs[0].duration_in_traffic.text')

echo "From $ORIGIN:"
echo "  Upper Level GWB: $upper_time"
echo "  Lower Level GWB: $lower_time"
