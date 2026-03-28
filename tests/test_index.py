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
                {"description": "123 Main St, Fort Lee, NJ", "place_id": "abc"},
            ],
            "status": "OK",
        }
        mock_get.return_value = mock_resp

        resp = client.get("/places/autocomplete", params={"input": "123 Main"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "OK"
        assert len(data["predictions"]) == 1



class TestInsightsEndpoints:
    def test_hourly_profile(self, test_client):
        client, _ = test_client
        with patch("index.api_client") as mock_api:
            mock_api.history.get_hourly_profile.return_value = [
                {"hour_of_day": 8, "avg_seconds": 480, "median_seconds": 460,
                 "min_seconds": 300, "max_seconds": 700, "sample_count": 25},
            ]
            resp = client.get("/history/upper_nj_to_nyc/hourly?filter=weekday")
            assert resp.status_code == 200
            data = resp.json()
            assert data["route_name"] == "upper_nj_to_nyc"
            assert data["filter"] == "weekday"
            assert len(data["hours"]) == 1
            assert data["hours"][0]["hour_of_day"] == 8

    def test_hourly_profile_invalid_filter(self, test_client):
        client, _ = test_client
        resp = client.get("/history/upper_nj_to_nyc/hourly?filter=invalid")
        assert resp.status_code == 422

    def test_heatmap(self, test_client):
        client, _ = test_client
        with patch("index.api_client") as mock_api:
            mock_api.history.get_heatmap.return_value = [
                {"day_of_week": 0, "hour_of_day": 8, "avg_seconds": 500, "sample_count": 10},
            ]
            resp = client.get("/history/upper_nj_to_nyc/heatmap")
            assert resp.status_code == 200
            data = resp.json()
            assert len(data["cells"]) == 1

    def test_peak_comparison(self, test_client):
        client, _ = test_client
        with patch("index.api_client") as mock_api:
            mock_api.history.get_peak_comparison.return_value = {
                "peak": {"avg_seconds": 600, "median_seconds": 580, "sample_count": 50},
                "off_peak": {"avg_seconds": 400, "median_seconds": 390, "sample_count": 100},
            }
            resp = client.get("/history/upper_nj_to_nyc/peak")
            assert resp.status_code == 200
            data = resp.json()
            assert data["peak"]["avg_seconds"] == 600
            assert data["off_peak"]["avg_seconds"] == 400

    def test_peak_comparison_empty(self, test_client):
        client, _ = test_client
        with patch("index.api_client") as mock_api:
            mock_api.history.get_peak_comparison.return_value = {}
            resp = client.get("/history/upper_nj_to_nyc/peak")
            assert resp.status_code == 200
            data = resp.json()
            assert data["peak"] is None
            assert data["off_peak"] is None

    def test_trend(self, test_client):
        client, _ = test_client
        with patch("index.api_client") as mock_api:
            mock_api.history.get_trend.return_value = {
                "recent_days": 7, "baseline_days": 30,
                "recent": {"avg_seconds": 500, "sample_count": 20},
                "baseline": {"avg_seconds": 480, "sample_count": 80},
                "change_pct": 4.2,
            }
            resp = client.get("/history/upper_nj_to_nyc/trend")
            assert resp.status_code == 200
            data = resp.json()
            assert data["change_pct"] == 4.2

    def test_route_comparison(self, test_client):
        client, _ = test_client
        with patch("index.api_client") as mock_api:
            mock_api.history.get_route_comparison.return_value = [
                {"route_name": "upper_nj_to_nyc", "avg_seconds": 450, "median_seconds": 440,
                 "min_seconds": 300, "max_seconds": 600, "sample_count": 50},
                {"route_name": "lower_nj_to_nyc", "avg_seconds": 480, "median_seconds": 470,
                 "min_seconds": 310, "max_seconds": 650, "sample_count": 45},
            ]
            resp = client.get("/history/compare/nj_to_nyc")
            assert resp.status_code == 200
            data = resp.json()
            assert data["direction"] == "nj_to_nyc"
            assert len(data["routes"]) == 2

    def test_route_comparison_invalid_direction(self, test_client):
        client, _ = test_client
        resp = client.get("/history/compare/invalid_dir")
        assert resp.status_code == 400


class TestCronCollect:
    def test_cron_collect_success(self, test_client):
        client, _ = test_client
        with patch("index.api_client") as mock_api:
            mock_api.get_times_as_model.return_value = Mock(
                upper_level_nyc="5 mins",
                lower_level_nyc="6 mins",
                upper_level_nj="4 mins",
                lower_level_nj="7 mins",
            )
            resp = client.get("/cron/collect")
            assert resp.status_code == 200
            data = resp.json()
            assert data["status"] == "ok"
            assert data["recorded"]["upper_nj_to_nyc"] == "5 mins"

    def test_cron_collect_rejects_bad_secret(self, test_client):
        client, _ = test_client
        with patch.dict(os.environ, {"CRON_SECRET": "my-secret"}):
            resp = client.get("/cron/collect", headers={"Authorization": "Bearer wrong"})
            assert resp.status_code == 401

    def test_cron_collect_allows_correct_secret(self, test_client):
        client, _ = test_client
        with patch.dict(os.environ, {"CRON_SECRET": "my-secret"}):
            with patch("index.api_client") as mock_api:
                mock_api.get_times_as_model.return_value = Mock(
                    upper_level_nyc="5 mins",
                    lower_level_nyc="6 mins",
                    upper_level_nj="4 mins",
                    lower_level_nj="7 mins",
                )
                resp = client.get("/cron/collect", headers={"Authorization": "Bearer my-secret"})
                assert resp.status_code == 200


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
