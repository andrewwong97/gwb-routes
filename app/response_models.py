from typing import List, Optional
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


class TimeWindow(BaseModel):
    day_of_week: int        # 0=Monday, 6=Sunday
    hour_of_day: int        # 0-23
    minute_bucket: int      # 0, 15, 30, 45
    avg_seconds: int
    median_seconds: int
    sample_count: int


class BestTimesResponse(BaseModel):
    route_name: str
    day_of_week: Optional[int] = None
    windows: List[TimeWindow]


class DailySummary(BaseModel):
    day_of_week: int
    avg_seconds: int
    median_seconds: int
    min_seconds: int
    max_seconds: int
    sample_count: int


class DailySummaryResponse(BaseModel):
    route_name: str
    days: List[DailySummary]


class TrackedRoute(BaseModel):
    name: str
    id: int
    record_count: int
    first_recorded: Optional[str] = None
    last_recorded: Optional[str] = None


class DurationRecord(BaseModel):
    duration_seconds: int
    captured_at: str
    day_of_week: int
    hour_of_day: int
    minute_bucket: int


class TimeSeriesResponse(BaseModel):
    route_name: str
    records: List[DurationRecord]


# ── Insights models ───────────────────────────────────────────────────

class HourlyBucket(BaseModel):
    hour_of_day: int
    avg_seconds: int
    median_seconds: int
    min_seconds: int
    max_seconds: int
    sample_count: int


class HourlyProfileResponse(BaseModel):
    route_name: str
    filter: str  # "all", "weekday", "weekend"
    hours: List[HourlyBucket]


class HeatmapCell(BaseModel):
    day_of_week: int
    hour_of_day: int
    avg_seconds: int
    sample_count: int


class HeatmapResponse(BaseModel):
    route_name: str
    cells: List[HeatmapCell]


class PeriodStats(BaseModel):
    avg_seconds: int
    median_seconds: int
    sample_count: int


class PeakComparisonResponse(BaseModel):
    route_name: str
    peak: Optional[PeriodStats] = None
    off_peak: Optional[PeriodStats] = None


class TrendPeriod(BaseModel):
    avg_seconds: int
    sample_count: int


class TrendResponse(BaseModel):
    route_name: str
    recent_days: int
    baseline_days: int
    recent: Optional[TrendPeriod] = None
    baseline: Optional[TrendPeriod] = None
    change_pct: Optional[float] = None


class RouteComparisonEntry(BaseModel):
    route_name: str
    avg_seconds: int
    median_seconds: int
    min_seconds: int
    max_seconds: int
    sample_count: int


class RouteComparisonResponse(BaseModel):
    direction: str
    routes: List[RouteComparisonEntry]