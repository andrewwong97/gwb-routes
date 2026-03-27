from constants import (
    gwb_upper_nj_side, gwb_lower_nj_side,
    gwb_upper_nyc_side, gwb_lower_nyc_side,
    gwb_off_ramp_upper_nj_side, gwb_off_ramp_lower_nj_side,
    gwb_off_ramp_upper_nyc_side, gwb_off_ramp_lower_nyc_side,
)
from datamodels.location import Location


ALL_LOCATIONS = [
    gwb_upper_nj_side, gwb_lower_nj_side,
    gwb_upper_nyc_side, gwb_lower_nyc_side,
    gwb_off_ramp_upper_nj_side, gwb_off_ramp_lower_nj_side,
    gwb_off_ramp_upper_nyc_side, gwb_off_ramp_lower_nyc_side,
]


class TestConstants:
    def test_all_locations_are_location_instances(self):
        for loc in ALL_LOCATIONS:
            assert isinstance(loc, Location)

    def test_all_locations_have_names(self):
        for loc in ALL_LOCATIONS:
            assert loc.get_name() is not None
            assert len(loc.get_name()) > 0

    def test_coordinates_in_gwb_area(self):
        """All coordinates should be near the George Washington Bridge."""
        for loc in ALL_LOCATIONS:
            assert 40.84 < loc.lat < 40.86, f"{loc.get_name()} lat {loc.lat} out of range"
            assert -73.97 < loc.lon < -73.94, f"{loc.get_name()} lon {loc.lon} out of range"

    def test_nj_side_is_west_of_nyc_side(self):
        """NJ-side coordinates should have more negative longitude (further west)."""
        assert gwb_upper_nj_side.lon < gwb_upper_nyc_side.lon
        assert gwb_lower_nj_side.lon < gwb_lower_nyc_side.lon

    def test_to_key_returns_valid_strings(self):
        for loc in ALL_LOCATIONS:
            key = loc.to_key()
            parts = key.split(",")
            assert len(parts) == 2
            float(parts[0])  # should not raise
            float(parts[1])  # should not raise

    def test_all_eight_locations_defined(self):
        assert len(ALL_LOCATIONS) == 8
