import re
import requests
import logging
try:
    from .response_models import GWBRoutes, RouteRecommendation
    from .constants import *
    from .routes_cache import RoutesCache
    from .datamodels.location import Location
except ImportError:
    from response_models import GWBRoutes, RouteRecommendation
    from constants import *
    from routes_cache import RoutesCache
    from datamodels.location import Location

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

class ApiClient:
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.cache = RoutesCache()

    def get_duration(self, origin: Location, dest: Location):
        """ Returns the duration of the route in traffic in human-readable format """
        
        # Check cache first and return early if found
        cached_duration = self.cache.get(origin, dest)
        if cached_duration:
            return cached_duration

        base_url = "https://maps.googleapis.com/maps/api/directions/json"
        params = {
            "origin": origin.to_key(),
            "destination": dest.to_key(),
            "mode": "driving",
            "units": "imperial",
            "departure_time": "now",
            "traffic_model": "best_guess",
            "key": self.api_key,
        }
        resp = requests.get(base_url, params=params)
        log.info("Made API call to Google Maps API")
        data = resp.json()
        try:
            route_duration = data["routes"][0]["legs"][0]["duration_in_traffic"]["text"]
            
            # Cache the result
            self.cache.set(origin, dest, route_duration)
                    
            return route_duration
        except (KeyError, IndexError):
            return "N/A"
    
    def clear_cache(self, pattern: str = "route:*"):
        """Clear cache entries matching the pattern"""
        return self.cache.clear_cache(pattern)
    
    def get_cache_info(self):
        """Get information about cached routes"""
        return self.cache.get_cache_info()
    
    def cache_health_check(self):
        """Perform a health check on the cache"""
        return self.cache.health_check()

    def get_times_as_model(self) -> GWBRoutes:
        return GWBRoutes(
            # NJ to NYC
            upper_level_nyc = self.get_duration(gwb_upper_nj_side, gwb_off_ramp_upper_nyc_side),
            lower_level_nyc = self.get_duration(gwb_lower_nj_side, gwb_off_ramp_lower_nyc_side),

            # NYC to NJ
            upper_level_nj = self.get_duration(gwb_upper_nyc_side, gwb_off_ramp_upper_nj_side),
            lower_level_nj = self.get_duration(gwb_lower_nyc_side, gwb_off_ramp_lower_nj_side)
        )
        
    def _get_raw_duration(self, origin_str: str, dest_str: str) -> tuple:
        """Call Directions API with raw address/coordinate strings.
        Returns (text, seconds) or ("N/A", inf) on error."""
        base_url = "https://maps.googleapis.com/maps/api/directions/json"
        params = {
            "origin": origin_str,
            "destination": dest_str,
            "mode": "driving",
            "units": "imperial",
            "departure_time": "now",
            "traffic_model": "best_guess",
            "key": self.api_key,
        }
        try:
            resp = requests.get(base_url, params=params)
            data = resp.json()
            leg = data["routes"][0]["legs"][0]
            text = leg["duration_in_traffic"]["text"]
            value = leg["duration_in_traffic"]["value"]
            return (text, value)
        except (KeyError, IndexError, Exception):
            return ("N/A", float("inf"))

    def places_autocomplete(self, input_text: str) -> dict:
        """Return place predictions for the given input text."""
        url = "https://maps.googleapis.com/maps/api/place/autocomplete/json"
        params = {
            "input": input_text,
            "components": "country:us",
            "key": self.api_key,
        }
        try:
            resp = requests.get(url, params=params)
            data = resp.json()
            status = data.get("status", "UNKNOWN")
            if status != "OK":
                log.warning(f"Places API status: {status}, error: {data.get('error_message', 'none')}")
                return {"predictions": [], "status": status, "error": data.get("error_message")}
            return {
                "predictions": [
                    {"description": p["description"], "place_id": p["place_id"]}
                    for p in data.get("predictions", [])
                ],
                "status": "OK",
            }
        except Exception as e:
            log.error(f"Places autocomplete error: {e}")
            return {"predictions": [], "status": "ERROR", "error": str(e)}

    def _geocode(self, address: str) -> tuple:
        """Returns (lat, lon) for an address string, or None on failure.
        Uses the Directions API (already required for bridge times) so that
        the Geocoding API does not need to be separately enabled on the key."""
        base_url = "https://maps.googleapis.com/maps/api/directions/json"
        params = {
            "origin": address,
            "destination": gwb_upper_nj_side.to_key(),
            "mode": "driving",
            "key": self.api_key,
        }
        try:
            resp = requests.get(base_url, params=params)
            data = resp.json()
            loc = data["routes"][0]["legs"][0]["start_location"]
            return (loc["lat"], loc["lng"])
        except (KeyError, IndexError, Exception):
            return None

    @staticmethod
    def _parse_duration_text(text: str) -> float:
        """Convert '25 mins' or '1 hour 5 mins' to seconds. Returns inf on N/A."""
        if not text or text == "N/A":
            return float("inf")
        total = 0
        hour_match = re.search(r"(\d+)\s+hour", text)
        min_match = re.search(r"(\d+)\s+min", text)
        if hour_match:
            total += int(hour_match.group(1)) * 3600
        if min_match:
            total += int(min_match.group(1)) * 60
        return total if total > 0 else float("inf")

    @staticmethod
    def _format_seconds(seconds: float) -> str:
        """Convert seconds to a compact human-readable string."""
        if seconds == float("inf"):
            return "N/A"
        seconds = int(seconds)
        hours = seconds // 3600
        minutes = (seconds % 3600) // 60
        if hours > 0:
            return f"{hours} hr {minutes} min"
        return f"{minutes} min"

    def get_route_recommendation(self, origin: str, destination: str) -> RouteRecommendation:
        """Return the recommended GWB level (upper/lower) for a given origin → destination trip."""
        # Geocode origin to determine which side of the bridge the user is starting from
        coords = self._geocode(origin)
        if coords is None:
            raise ValueError(f"Could not geocode origin address: {origin}")

        origin_lon = coords[1]
        # The GWB spans roughly -73.953 (NYC side) to -73.967 (NJ side)
        # Anything west of -73.953 is treated as coming from / on the NJ side
        GWB_MID_LON = -73.953

        if origin_lon < GWB_MID_LON:
            direction = "NJ → NYC"
            upper_on_ramp  = gwb_upper_nj_side
            lower_on_ramp  = gwb_lower_nj_side
            upper_off_ramp = gwb_off_ramp_upper_nyc_side
            lower_off_ramp = gwb_off_ramp_lower_nyc_side
        else:
            direction = "NYC → NJ"
            upper_on_ramp  = gwb_upper_nyc_side
            lower_on_ramp  = gwb_lower_nyc_side
            upper_off_ramp = gwb_off_ramp_upper_nj_side
            lower_off_ramp = gwb_off_ramp_lower_nj_side

        # Bridge crossing times (served from cache when available)
        if direction == "NJ → NYC":
            upper_bridge = self.get_duration(gwb_upper_nj_side, gwb_off_ramp_upper_nyc_side)
            lower_bridge = self.get_duration(gwb_lower_nj_side, gwb_off_ramp_lower_nyc_side)
        else:
            upper_bridge = self.get_duration(gwb_upper_nyc_side, gwb_off_ramp_upper_nj_side)
            lower_bridge = self.get_duration(gwb_lower_nyc_side, gwb_off_ramp_lower_nj_side)

        # Legs before and after the bridge
        upper_to_bridge,   upper_to_secs   = self._get_raw_duration(origin,                    upper_on_ramp.to_key())
        lower_to_bridge,   lower_to_secs   = self._get_raw_duration(origin,                    lower_on_ramp.to_key())
        upper_from_bridge, upper_from_secs = self._get_raw_duration(upper_off_ramp.to_key(),   destination)
        lower_from_bridge, lower_from_secs = self._get_raw_duration(lower_off_ramp.to_key(),   destination)

        upper_bridge_secs = self._parse_duration_text(upper_bridge)
        lower_bridge_secs = self._parse_duration_text(lower_bridge)

        upper_total_secs = upper_to_secs + upper_bridge_secs + upper_from_secs
        lower_total_secs = lower_to_secs + lower_bridge_secs + lower_from_secs

        upper_total = self._format_seconds(upper_total_secs)
        lower_total = self._format_seconds(lower_total_secs)

        if upper_total_secs <= lower_total_secs:
            recommended = "upper"
            saved_secs = lower_total_secs - upper_total_secs
        else:
            recommended = "lower"
            saved_secs = upper_total_secs - lower_total_secs

        time_saved = self._format_seconds(saved_secs) if saved_secs > 60 else "same time"

        return RouteRecommendation(
            recommended_level=recommended,
            direction=direction,
            upper_total=upper_total,
            lower_total=lower_total,
            upper_to_bridge=upper_to_bridge,
            upper_bridge=upper_bridge,
            upper_from_bridge=upper_from_bridge,
            lower_to_bridge=lower_to_bridge,
            lower_bridge=lower_bridge,
            lower_from_bridge=lower_from_bridge,
            time_saved=time_saved,
        )

    def get_times_as_text(self):
        # NJ to NYC direction (GWB NJ-side ramps → NYC location)
        upper_time_to_nyc = self.get_duration(gwb_upper_nj_side, gwb_off_ramp_upper_nyc_side)
        lower_time_to_nyc = self.get_duration(gwb_lower_nj_side, gwb_off_ramp_lower_nyc_side)
        
        # NYC to NJ direction (GWB NYC-side ramps → NJ location)
        upper_time_to_nj = self.get_duration(gwb_upper_nyc_side, gwb_off_ramp_upper_nj_side)
        lower_time_to_nj = self.get_duration(gwb_lower_nyc_side, gwb_off_ramp_lower_nj_side)

        response_text = f"""
------------------------------------
NJ to NYC:
------------------------------------
    Upper Level GWB: {upper_time_to_nyc}
    Lower Level GWB: {lower_time_to_nyc}

------------------------------------
NYC to NJ:
------------------------------------
    Upper Level GWB: {upper_time_to_nj}
    Lower Level GWB: {lower_time_to_nj}
        """
        return response_text