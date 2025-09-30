import requests
import logging
try:
    from .models import GWBRoutes
    from .constants import *
    from .routes_cache import RoutesCache
except ImportError:
    from models import GWBRoutes
    from constants import *
    from routes_cache import RoutesCache

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

class ApiClient:
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.cache = RoutesCache()

    def get_duration(self, origin, dest):
        """ Returns the duration of the route in traffic in human-readable format """
        
        # Check cache first and return early if found
        cached_duration = self.cache.get(origin, dest)
        if cached_duration:
            return cached_duration

        base_url = "https://maps.googleapis.com/maps/api/directions/json"
        params = {
            "origin": origin,
            "destination": dest,
            "mode": "driving",
            "units": "imperial",
            "departure_time": "now",
            "traffic_model": "best_guess",
            "key": self.api_key,
        }
        resp = requests.get(base_url, params=params)
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