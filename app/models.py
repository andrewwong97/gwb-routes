from pydantic import BaseModel

class GWBRoutes(BaseModel):
    upper_level_nyc: str
    lower_level_nyc: str
    upper_level_nj: str
    lower_level_nj: str