import os
import pytest
from unittest.mock import Mock, patch
try:
    from .routes_cache import RoutesCache
except ImportError:
    from routes_cache import RoutesCache


class MockRedis:
    """Dictionary-based Redis mock for integration testing"""
    
    def __init__(self):
        self.data = {}
        self.ttls = {}
    
    def get(self, key):
        if key in self.data:
            return self.data[key].encode() if isinstance(self.data[key], str) else self.data[key]
        return None
    
    def setex(self, key, ttl, value):
        self.data[key] = value
        self.ttls[key] = ttl
        return True
    
    def keys(self, pattern):
        if pattern == "route:*":
            return [k.encode() for k in self.data.keys() if k.startswith("route:")]
        return []
    
    def delete(self, *keys):
        deleted = 0
        for key in keys:
            if isinstance(key, bytes):
                key = key.decode()
            if key in self.data:
                del self.data[key]
                self.ttls.pop(key, None)
                deleted += 1
        return deleted
    
    def ttl(self, key):
        return self.ttls.get(key.decode() if isinstance(key, bytes) else key, -1)
    
    def ping(self):
        return True
    
    def info(self):
        return {"used_memory_human": f"{len(self.data)}KB"}


class TestRoutesCacheIntegration:
    """Integration test covering all critical RoutesCache functionality"""

    @patch.dict(os.environ, {"REDIS_URL": "redis://test", "CACHE_TTL": "300"})
    @patch('routes_cache.Redis.from_url')
    def test_routes_cache_complete_workflow(self, mock_from_url):
        """Test complete RoutesCache workflow: initialization, caching, retrieval, management"""
        mock_redis = MockRedis()
        mock_from_url.return_value = mock_redis
        
        # Test initialization with Redis URL
        cache = RoutesCache()
        assert cache.redis_url == "redis://test"
        assert cache.cache_ttl == 300
        assert cache.is_available() is True
        
        # Test cache miss
        result = cache.get("origin1", "dest1")
        assert result is None
        
        # Test cache set
        success = cache.set("origin1", "dest1", "15 mins")
        assert success is True
        
        # Test cache hit
        result = cache.get("origin1", "dest1")
        assert result == "15 mins"
        
        # Test multiple cache entries
        cache.set("origin2", "dest2", "20 mins")
        cache.set("origin3", "dest3", "25 mins")
        assert len(mock_redis.data) == 3
        
        # Test cache info
        info = cache.get_cache_info()
        assert info["total_cached_routes"] == 3
        assert info["cache_ttl_seconds"] == 300
        assert info["redis_connected"] is True
        assert "redis_memory_usage" in info
        
        # Test health check
        health = cache.health_check()
        assert health["healthy"] is True
        assert health["cache_ttl"] == 300
        
        # Test cache clearing
        cleared = cache.clear_cache("route:*")
        assert cleared == 3
        assert len(mock_redis.data) == 0
        
        # Test cache miss after clear
        result = cache.get("origin1", "dest1")
        assert result is None

    @patch.dict(os.environ, {}, clear=True)
    def test_routes_cache_without_redis(self):
        """Test RoutesCache behavior when Redis is not configured"""
        cache = RoutesCache()
        
        # Test initialization without Redis
        assert cache.redis_url is None
        assert cache.cache_ttl == 300  # default
        assert cache.is_available() is False
        
        # Test operations without Redis
        assert cache.get("origin", "dest") is None
        assert cache.set("origin", "dest", "value") is False
        assert cache.clear_cache() == 0
        
        # Test info and health without Redis
        info = cache.get_cache_info()
        assert info == {"status": "Redis not available"}
        
        health = cache.health_check()
        assert health["healthy"] is False
        assert health["reason"] == "Redis not connected"

    @patch.dict(os.environ, {"REDIS_URL": "redis://test"})
    @patch('routes_cache.Redis.from_url')
    def test_routes_cache_redis_errors(self, mock_from_url):
        """Test RoutesCache error handling"""
        mock_redis = Mock()
        mock_redis.info.return_value = {}
        
        # Test Redis operation errors
        mock_redis.get.side_effect = Exception("Redis get error")
        mock_redis.setex.side_effect = Exception("Redis setex error")
        mock_redis.keys.side_effect = Exception("Redis keys error")
        mock_redis.ping.side_effect = Exception("Redis ping error")
        
        mock_from_url.return_value = mock_redis
        
        cache = RoutesCache()
        
        # All operations should handle errors gracefully
        assert cache.get("origin", "dest") is None
        assert cache.set("origin", "dest", "value") is False
        assert cache.clear_cache() == 0
        
        health = cache.health_check()
        assert health["healthy"] is False
        assert "Redis ping error" in health["reason"]