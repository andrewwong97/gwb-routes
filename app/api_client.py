import requests
try:
    from .models import GWBRoutes
    from .constants import *
except ImportError:
    from models import GWBRoutes
    from constants import *


class ApiClient:
    def __init__(self, api_key: str):
        self.api_key = api_key

    def get_duration(self, origin, dest):
        """ Returns the duration of the route in traffic in human-readable format """
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
            return data["routes"][0]["legs"][0]["duration_in_traffic"]["text"]
        except (KeyError, IndexError):
            return "N/A"

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