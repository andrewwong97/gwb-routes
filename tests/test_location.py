from datamodels.location import Location


class TestLocation:
    def test_init_with_name(self):
        loc = Location(40.85, -73.96, "Test Location")
        assert loc.lat == 40.85
        assert loc.lon == -73.96
        assert loc.name == "Test Location"

    def test_init_without_name_defaults_to_coords(self):
        loc = Location(40.85, -73.96)
        assert loc.name == "40.85,-73.96"

    def test_to_key(self):
        loc = Location(40.85, -73.96, "Test")
        assert loc.to_key() == "40.85,-73.96"

    def test_get_name(self):
        loc = Location(40.85, -73.96, "My Location")
        assert loc.get_name() == "My Location"

    def test_str(self):
        loc = Location(40.85, -73.96, "Bridge")
        assert str(loc) == "Bridge: 40.85, -73.96"

    def test_repr(self):
        loc = Location(40.85, -73.96, "Bridge")
        assert repr(loc) == "Location(lat=40.85, lon=-73.96, name=Bridge)"

    def test_to_key_preserves_precision(self):
        loc = Location(40.85417910370559, -73.96578839657144, "Precise")
        key = loc.to_key()
        assert "40.85417910370559" in key
        assert "-73.96578839657144" in key
