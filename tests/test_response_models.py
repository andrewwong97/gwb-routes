import pytest
from pydantic import ValidationError
from response_models import GWBRoutes, RouteRecommendation


class TestGWBRoutes:
    def test_valid_construction(self):
        routes = GWBRoutes(
            upper_level_nyc="15 mins",
            lower_level_nyc="18 mins",
            upper_level_nj="12 mins",
            lower_level_nj="14 mins",
        )
        assert routes.upper_level_nyc == "15 mins"
        assert routes.lower_level_nyc == "18 mins"
        assert routes.upper_level_nj == "12 mins"
        assert routes.lower_level_nj == "14 mins"

    def test_serialization(self):
        routes = GWBRoutes(
            upper_level_nyc="15 mins",
            lower_level_nyc="18 mins",
            upper_level_nj="12 mins",
            lower_level_nj="14 mins",
        )
        data = routes.model_dump()
        assert data == {
            "upper_level_nyc": "15 mins",
            "lower_level_nyc": "18 mins",
            "upper_level_nj": "12 mins",
            "lower_level_nj": "14 mins",
        }

    def test_missing_field_raises(self):
        with pytest.raises(ValidationError):
            GWBRoutes(upper_level_nyc="15 mins")

    def test_json_roundtrip(self):
        routes = GWBRoutes(
            upper_level_nyc="15 mins",
            lower_level_nyc="18 mins",
            upper_level_nj="12 mins",
            lower_level_nj="14 mins",
        )
        json_str = routes.model_dump_json()
        restored = GWBRoutes.model_validate_json(json_str)
        assert restored == routes


class TestRouteRecommendation:
    def test_valid_construction(self):
        rec = RouteRecommendation(
            recommended_level="upper",
            direction="NJ → NYC",
            upper_total="25 min",
            lower_total="30 min",
            upper_to_bridge="5 mins",
            upper_bridge="15 mins",
            upper_from_bridge="5 mins",
            lower_to_bridge="6 mins",
            lower_bridge="18 mins",
            lower_from_bridge="6 mins",
            time_saved="5 min",
        )
        assert rec.recommended_level == "upper"
        assert rec.direction == "NJ → NYC"
        assert rec.time_saved == "5 min"

    def test_serialization_has_all_fields(self):
        rec = RouteRecommendation(
            recommended_level="lower",
            direction="NYC → NJ",
            upper_total="30 min",
            lower_total="25 min",
            upper_to_bridge="6 mins",
            upper_bridge="18 mins",
            upper_from_bridge="6 mins",
            lower_to_bridge="5 mins",
            lower_bridge="15 mins",
            lower_from_bridge="5 mins",
            time_saved="5 min",
        )
        data = rec.model_dump()
        expected_keys = {
            "recommended_level", "direction", "upper_total", "lower_total",
            "upper_to_bridge", "upper_bridge", "upper_from_bridge",
            "lower_to_bridge", "lower_bridge", "lower_from_bridge", "time_saved",
        }
        assert set(data.keys()) == expected_keys

    def test_missing_field_raises(self):
        with pytest.raises(ValidationError):
            RouteRecommendation(recommended_level="upper")
