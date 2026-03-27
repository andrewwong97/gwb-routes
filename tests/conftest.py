import os
import sys
import pytest
from unittest.mock import patch, Mock

# Add app directory to path so tests can import app modules
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'app'))


@pytest.fixture
def mock_env():
    """Provide a clean environment with required env vars for testing."""
    with patch.dict(os.environ, {
        "GOOGLE_MAPS_API_KEY": "test-api-key",
        "REDIS_URL": "",
        "SENTRY_DSN": "",
    }, clear=False):
        yield


@pytest.fixture
def mock_directions_response():
    """Factory for mock Google Maps Directions API responses."""
    def _make(duration_text="15 mins", duration_value=900):
        return {
            "routes": [{
                "legs": [{
                    "duration_in_traffic": {
                        "text": duration_text,
                        "value": duration_value,
                    },
                    "start_location": {"lat": 40.85, "lng": -73.96},
                }]
            }],
            "status": "OK",
        }
    return _make


@pytest.fixture
def mock_places_response():
    """Factory for mock Google Places Autocomplete responses."""
    def _make(predictions=None):
        if predictions is None:
            predictions = [
                {"description": "123 Main St, NJ", "place_id": "abc123"},
                {"description": "456 Oak Ave, NJ", "place_id": "def456"},
            ]
        return {"predictions": predictions, "status": "OK"}
    return _make
