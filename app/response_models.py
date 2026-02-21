from pydantic import BaseModel

class GWBRoutes(BaseModel):
    upper_level_nyc: str
    lower_level_nyc: str
    upper_level_nj: str
    lower_level_nj: str


class RouteRecommendation(BaseModel):
    recommended_level: str       # "upper" or "lower"
    direction: str               # "NJ → NYC" or "NYC → NJ"
    upper_total: str
    lower_total: str
    upper_to_bridge: str
    upper_bridge: str
    upper_from_bridge: str
    lower_to_bridge: str
    lower_bridge: str
    lower_from_bridge: str
    time_saved: str