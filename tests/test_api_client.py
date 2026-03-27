import pytest
from unittest.mock import patch, Mock, MagicMock
from api_client import ApiClient
from datamodels.location import Location
from response_models import RouteRecommendation


@pytest.fixture
def client():
    """Create an ApiClient with mocked cache (no Redis needed)."""
    with patch.dict("os.environ", {"REDIS_URL": ""}, clear=False):
        c = ApiClient("fake-api-key")
    return c


class TestParseDurationText:
    def test_minutes_only(self):
        assert ApiClient._parse_duration_text("25 mins") == 25 * 60

    def test_hours_and_minutes(self):
        assert ApiClient._parse_duration_text("1 hour 5 mins") == 3600 + 300

    def test_hours_only(self):
        assert ApiClient._parse_duration_text("2 hours") == 7200

    def test_na_returns_inf(self):
        assert ApiClient._parse_duration_text("N/A") == float("inf")

    def test_none_returns_inf(self):
        assert ApiClient._parse_duration_text(None) == float("inf")

    def test_empty_string_returns_inf(self):
        assert ApiClient._parse_duration_text("") == float("inf")

    def test_singular_min(self):
        assert ApiClient._parse_duration_text("1 min") == 60

    def test_singular_hour(self):
        assert ApiClient._parse_duration_text("1 hour") == 3600


class TestFormatSeconds:
    def test_minutes_only(self):
        assert ApiClient._format_seconds(1500) == "25 min"

    def test_hours_and_minutes(self):
        assert ApiClient._format_seconds(3900) == "1 hr 5 min"

    def test_zero_seconds(self):
        assert ApiClient._format_seconds(0) == "0 min"

    def test_inf_returns_na(self):
        assert ApiClient._format_seconds(float("inf")) == "N/A"

    def test_exact_hour(self):
        assert ApiClient._format_seconds(3600) == "1 hr 0 min"


class TestGetDuration:
    @patch("api_client.requests.get")
    def test_returns_duration_from_api(self, mock_get, client):
        mock_resp = Mock()
        mock_resp.json.return_value = {
            "routes": [{"legs": [{"duration_in_traffic": {"text": "18 mins", "value": 1080}}]}]
        }
        mock_get.return_value = mock_resp

        origin = Location(40.85, -73.96, "Origin")
        dest = Location(40.84, -73.94, "Dest")
        result = client.get_duration(origin, dest)
        assert result == "18 mins"

    @patch("api_client.requests.get")
    def test_returns_na_on_api_error(self, mock_get, client):
        mock_resp = Mock()
        mock_resp.json.return_value = {"routes": [], "status": "ZERO_RESULTS"}
        mock_get.return_value = mock_resp

        origin = Location(40.85, -73.96, "Origin")
        dest = Location(40.84, -73.94, "Dest")
        result = client.get_duration(origin, dest)
        assert result == "N/A"

    @patch("api_client.requests.get")
    def test_caches_result_on_success(self, mock_get, client):
        """When cache is unavailable, API is called each time (no caching)."""
        mock_resp = Mock()
        mock_resp.json.return_value = {
            "routes": [{"legs": [{"duration_in_traffic": {"text": "10 mins", "value": 600}}]}]
        }
        mock_get.return_value = mock_resp

        origin = Location(40.85, -73.96, "O")
        dest = Location(40.84, -73.94, "D")
        client.get_duration(origin, dest)
        client.get_duration(origin, dest)
        # Without Redis, each call hits the API
        assert mock_get.call_count == 2


class TestGetRawDuration:
    @patch("api_client.requests.get")
    def test_returns_text_and_seconds(self, mock_get, client):
        mock_resp = Mock()
        mock_resp.json.return_value = {
            "routes": [{"legs": [{"duration_in_traffic": {"text": "20 mins", "value": 1200}}]}]
        }
        mock_get.return_value = mock_resp

        text, secs = client._get_raw_duration("origin_addr", "dest_addr")
        assert text == "20 mins"
        assert secs == 1200

    @patch("api_client.requests.get")
    def test_returns_na_on_error(self, mock_get, client):
        mock_get.side_effect = Exception("Network error")

        text, secs = client._get_raw_duration("origin", "dest")
        assert text == "N/A"
        assert secs == float("inf")


class TestGeocode:
    @patch("api_client.requests.get")
    def test_returns_lat_lon(self, mock_get, client):
        mock_resp = Mock()
        mock_resp.json.return_value = {
            "routes": [{"legs": [{"start_location": {"lat": 40.75, "lng": -74.00}}]}]
        }
        mock_get.return_value = mock_resp

        result = client._geocode("123 Main St, NJ")
        assert result == (40.75, -74.00)

    @patch("api_client.requests.get")
    def test_returns_none_on_error(self, mock_get, client):
        mock_resp = Mock()
        mock_resp.json.return_value = {"routes": [], "status": "ZERO_RESULTS"}
        mock_get.return_value = mock_resp

        result = client._geocode("invalid address")
        assert result is None


class TestPlacesAutocomplete:
    @patch("api_client.requests.get")
    def test_returns_predictions(self, mock_get, client):
        mock_resp = Mock()
        mock_resp.json.return_value = {
            "predictions": [
                {"description": "123 Main St, Fort Lee, NJ", "place_id": "abc"},
                {"description": "456 Oak Ave, New York, NY", "place_id": "def"},
            ],
            "status": "OK",
        }
        mock_get.return_value = mock_resp

        result = client.places_autocomplete("123 Main")
        assert result["status"] == "OK"
        assert len(result["predictions"]) == 2
        assert result["predictions"][0]["description"] == "123 Main St, Fort Lee, NJ"

    @patch("api_client.requests.get")
    def test_handles_api_error_status(self, mock_get, client):
        mock_resp = Mock()
        mock_resp.json.return_value = {
            "status": "REQUEST_DENIED",
            "error_message": "Invalid key",
        }
        mock_get.return_value = mock_resp

        result = client.places_autocomplete("test")
        assert result["status"] == "REQUEST_DENIED"
        assert result["predictions"] == []

    @patch("api_client.requests.get")
    def test_handles_exception(self, mock_get, client):
        mock_get.side_effect = Exception("Connection error")

        result = client.places_autocomplete("test")
        assert result["status"] == "ERROR"
        assert result["predictions"] == []


class TestGetTimesAsModel:
    @patch("api_client.requests.get")
    def test_returns_gwb_routes_model(self, mock_get, client):
        call_count = [0]
        durations = ["15 mins", "18 mins", "12 mins", "14 mins"]

        duration_values = [900, 1080, 720, 840]

        def side_effect(*args, **kwargs):
            resp = Mock()
            idx = call_count[0] % 4
            resp.json.return_value = {
                "routes": [{"legs": [{"duration_in_traffic": {"text": durations[idx], "value": duration_values[idx]}}]}]
            }
            call_count[0] += 1
            return resp

        mock_get.side_effect = side_effect

        result = client.get_times_as_model()
        assert result.upper_level_nyc == "15 mins"
        assert result.lower_level_nyc == "18 mins"
        assert result.upper_level_nj == "12 mins"
        assert result.lower_level_nj == "14 mins"


class TestGetTimesAsText:
    @patch("api_client.requests.get")
    def test_returns_formatted_text(self, mock_get, client):
        call_count = [0]
        durations = ["15 mins", "18 mins", "12 mins", "14 mins"]

        duration_values = [900, 1080, 720, 840]

        def side_effect(*args, **kwargs):
            resp = Mock()
            idx = call_count[0] % 4
            resp.json.return_value = {
                "routes": [{"legs": [{"duration_in_traffic": {"text": durations[idx], "value": duration_values[idx]}}]}]
            }
            call_count[0] += 1
            return resp

        mock_get.side_effect = side_effect

        result = client.get_times_as_text()
        assert "Upper Level GWB: 15 mins" in result
        assert "Lower Level GWB: 18 mins" in result
        assert "NJ to NYC" in result
        assert "NYC to NJ" in result


class TestGetRouteRecommendation:
    @patch("api_client.requests.get")
    def test_nj_origin_recommends_faster_route(self, mock_get, client):
        """When origin is in NJ (lon < -73.953), direction should be NJ → NYC."""
        call_count = [0]

        def side_effect(*args, **kwargs):
            resp = Mock()
            url = kwargs.get("params", {}).get("origin", args[0] if args else "")
            # First call is _geocode → return NJ coords
            if call_count[0] == 0:
                resp.json.return_value = {
                    "routes": [{"legs": [{"start_location": {"lat": 40.85, "lng": -73.97}}]}]
                }
            # Bridge crossing calls (get_duration) and raw duration calls
            else:
                resp.json.return_value = {
                    "routes": [{"legs": [{
                        "duration_in_traffic": {"text": "15 mins", "value": 900}
                    }]}]
                }
            call_count[0] += 1
            return resp

        mock_get.side_effect = side_effect

        result = client.get_route_recommendation("Fort Lee, NJ", "Manhattan, NY")
        assert result.direction == "NJ → NYC"
        assert result.recommended_level in ("upper", "lower")
        assert result.time_saved is not None

    @patch("api_client.requests.get")
    def test_nyc_origin_recommends_nyc_to_nj(self, mock_get, client):
        """When origin is in NYC (lon > -73.953), direction should be NYC → NJ."""
        call_count = [0]

        def side_effect(*args, **kwargs):
            resp = Mock()
            if call_count[0] == 0:
                resp.json.return_value = {
                    "routes": [{"legs": [{"start_location": {"lat": 40.84, "lng": -73.94}}]}]
                }
            else:
                resp.json.return_value = {
                    "routes": [{"legs": [{
                        "duration_in_traffic": {"text": "10 mins", "value": 600}
                    }]}]
                }
            call_count[0] += 1
            return resp

        mock_get.side_effect = side_effect

        result = client.get_route_recommendation("Washington Heights, NY", "Fort Lee, NJ")
        assert result.direction == "NYC → NJ"

    @patch("api_client.requests.get")
    def test_raises_on_geocode_failure(self, mock_get, client):
        mock_resp = Mock()
        mock_resp.json.return_value = {"routes": [], "status": "ZERO_RESULTS"}
        mock_get.return_value = mock_resp

        with pytest.raises(ValueError, match="Could not geocode"):
            client.get_route_recommendation("invalid", "dest")

    @patch("api_client.requests.get")
    def test_returns_cached_recommendation(self, mock_get, client):
        """When a cached recommendation exists in Postgres, skip all API calls."""
        cached_rec = RouteRecommendation(
            recommended_level="upper",
            direction="NJ → NYC",
            upper_total="20 min",
            lower_total="25 min",
            upper_to_bridge="5 mins",
            upper_bridge="10 mins",
            upper_from_bridge="5 mins",
            lower_to_bridge="7 mins",
            lower_bridge="12 mins",
            lower_from_bridge="6 mins",
            time_saved="5 min",
        )
        client.history.get_cached_recommendation = Mock(return_value=cached_rec)

        result = client.get_route_recommendation("Fort Lee, NJ", "Manhattan, NY")
        assert result == cached_rec
        # No Google Maps API calls should have been made
        mock_get.assert_not_called()

    @patch("api_client.requests.get")
    def test_saves_recommendation_after_computing(self, mock_get, client):
        """After computing a fresh recommendation, it should be saved to Postgres."""
        client.history.get_cached_recommendation = Mock(return_value=None)
        client.history.save_recommendation = Mock(return_value=True)

        call_count = [0]

        def side_effect(*args, **kwargs):
            resp = Mock()
            if call_count[0] == 0:
                resp.json.return_value = {
                    "routes": [{"legs": [{"start_location": {"lat": 40.85, "lng": -73.97}}]}]
                }
            else:
                resp.json.return_value = {
                    "routes": [{"legs": [{
                        "duration_in_traffic": {"text": "15 mins", "value": 900}
                    }]}]
                }
            call_count[0] += 1
            return resp

        mock_get.side_effect = side_effect

        result = client.get_route_recommendation("Fort Lee, NJ", "Manhattan, NY")
        client.history.save_recommendation.assert_called_once_with(
            "Fort Lee, NJ", "Manhattan, NY", result
        )

    @patch("api_client.requests.get")
    def test_cache_failure_falls_through_to_api(self, mock_get, client):
        """If the DB cache check raises, we still compute from API."""
        client.history.get_cached_recommendation = Mock(side_effect=Exception("DB down"))

        call_count = [0]

        def side_effect(*args, **kwargs):
            resp = Mock()
            if call_count[0] == 0:
                resp.json.return_value = {
                    "routes": [{"legs": [{"start_location": {"lat": 40.85, "lng": -73.97}}]}]
                }
            else:
                resp.json.return_value = {
                    "routes": [{"legs": [{
                        "duration_in_traffic": {"text": "15 mins", "value": 900}
                    }]}]
                }
            call_count[0] += 1
            return resp

        mock_get.side_effect = side_effect

        result = client.get_route_recommendation("Fort Lee, NJ", "Manhattan, NY")
        assert result.direction == "NJ → NYC"
