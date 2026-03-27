import os
import pytest
from unittest.mock import patch, Mock


# Must set env vars before importing index module
@pytest.fixture(autouse=True)
def _setup_env():
    with patch.dict(os.environ, {
        "GOOGLE_MAPS_API_KEY": "test-key",
        "SENTRY_DSN": "",
        "REDIS_URL": "",
    }):
        yield


@pytest.fixture
def test_client():
    """Create a FastAPI TestClient with mocked external dependencies."""
    with patch.dict(os.environ, {
        "GOOGLE_MAPS_API_KEY": "test-key",
        "SENTRY_DSN": "",
        "REDIS_URL": "",
    }):
        with patch("api_client.requests.get") as mock_get:
            mock_resp = Mock()
            mock_resp.json.return_value = {
                "routes": [{"legs": [{"duration_in_traffic": {"text": "15 mins", "value": 900}}]}]
            }
            mock_get.return_value = mock_resp

            from fastapi.testclient import TestClient
            from index import app
            client = TestClient(app)
            yield client, mock_get


class TestHealthcheck:
    def test_healthcheck(self, test_client):
        client, _ = test_client
        resp = client.get("/healthcheck")
        assert resp.status_code == 200
        assert resp.json() == {"status": "healthy"}


class TestTimesEndpoint:
    def test_times_returns_json(self, test_client):
        client, _ = test_client
        resp = client.get("/times")
        assert resp.status_code == 200
        data = resp.json()
        assert "upper_level_nyc" in data
        assert "lower_level_nyc" in data
        assert "upper_level_nj" in data
        assert "lower_level_nj" in data

    def test_times_has_cache_headers(self, test_client):
        client, _ = test_client
        resp = client.get("/times")
        assert "max-age=180" in resp.headers.get("cache-control", "")


class TestPlaintextEndpoint:
    def test_plaintext_returns_text(self, test_client):
        client, _ = test_client
        resp = client.get("/plaintext")
        assert resp.status_code == 200
        assert "Upper Level GWB" in resp.text
        assert "Lower Level GWB" in resp.text


class TestRecommendEndpoint:
    def test_recommend_requires_params(self, test_client):
        client, _ = test_client
        resp = client.get("/recommend")
        assert resp.status_code == 422  # Missing required query params

    def test_recommend_returns_recommendation(self, test_client):
        client, mock_get = test_client
        call_count = [0]

        def side_effect(*args, **kwargs):
            resp = Mock()
            if call_count[0] == 0:
                # geocode call
                resp.json.return_value = {
                    "routes": [{"legs": [{"start_location": {"lat": 40.85, "lng": -73.97}}]}]
                }
            else:
                resp.json.return_value = {
                    "routes": [{"legs": [{"duration_in_traffic": {"text": "15 mins", "value": 900}}]}]
                }
            call_count[0] += 1
            return resp

        mock_get.side_effect = side_effect

        resp = client.get("/recommend", params={"origin": "Fort Lee, NJ", "destination": "Manhattan, NY"})
        assert resp.status_code == 200
        data = resp.json()
        assert "recommended_level" in data
        assert "direction" in data


class TestPlacesAutocompleteEndpoint:
    def test_autocomplete_requires_input(self, test_client):
        client, _ = test_client
        resp = client.get("/places/autocomplete")
        assert resp.status_code == 422

    def test_autocomplete_min_length(self, test_client):
        client, _ = test_client
        resp = client.get("/places/autocomplete", params={"input": "a"})
        assert resp.status_code == 422

    def test_autocomplete_returns_predictions(self, test_client):
        client, mock_get = test_client
        mock_resp = Mock()
        mock_resp.json.return_value = {
            "predictions": [
                {"description": "123 Main St", "place_id": "abc"},
            ],
            "status": "OK",
        }
        mock_get.return_value = mock_resp

        resp = client.get("/places/autocomplete", params={"input": "123 Main"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "OK"
        assert len(data["predictions"]) == 1


class TestDashboard:
    def test_dashboard_root(self, test_client):
        client, _ = test_client
        resp = client.get("/")
        # May return 200 or 404 depending on static file availability
        assert resp.status_code in (200, 404)

    def test_dashboard_path(self, test_client):
        client, _ = test_client
        resp = client.get("/dashboard")
        assert resp.status_code in (200, 404)
