import os
import logging
from redis import Redis
from typing import Optional

try:
    from .datamodels.location import Location
except ImportError:
    from datamodels.location import Location

log = logging.getLogger(__name__)


class RoutesCache:
    """Redis-based cache for route value data with TTL support"""
    
    def __init__(self):
        self.redis_url = os.getenv("REDIS_URL")
        self.cache_ttl = 180    # 3 minutes
        self.redis = None
        
        if self.redis_url:
            self._connect()
        else:
            log.warning("REDIS_URL is not set, cache will be disabled")
    
    def _connect(self):
        """Initialize Redis connection with error handling"""
        try:
            self.redis = Redis.from_url(self.redis_url)
            # Test connection and log Redis info
            info = self.redis.info()
            log.info(f"Connected to Redis. Memory usage: {info.get('used_memory_human', 'N/A')}")
        except Exception as e:
            log.error(f"Redis connection failed: {e}")
            self.redis = None
    
    def _generate_cache_key(self, origin: Location, dest: Location) -> str:
        """Generate a consistent cache key for origin-destination pair"""
        return f"route:{hash(f'{origin.to_key()}_{dest.to_key()}')}"
    
    def get(self, origin: Location, dest: Location) -> Optional[str]:
        """Get cached value for a route"""
        if not self.redis:
            log.error("Redis not connected")
            return None
            
        cache_key = self._generate_cache_key(origin, dest)
        
        try:
            cached_duration = self.redis.get(cache_key)
            if cached_duration:
                log.info(f"Cache hit for {origin.get_name()} → {dest.get_name()}")
                return cached_duration.decode("utf-8")
            else:
                log.info(f"Cache miss for {origin.get_name()} → {dest.get_name()}")
                return None
        except Exception as e:
            log.error(f"Redis get error: {e}")
            return None
    
    def set(self, origin: Location, dest: Location, value: str) -> bool:
        """Cache value for a route with TTL"""
        if not self.redis:
            return False
            
        cache_key = self._generate_cache_key(origin, dest)
        
        try:
            # Set with TTL in seconds
            self.redis.setex(cache_key, self.cache_ttl, value)
            log.info(f"Cached route for {self.cache_ttl}s: {origin.get_name()} → {dest.get_name()} = {value}")
            return True
        except Exception as e:
            log.error(f"Redis setex error: {e}")
            return False
    
    # For testing
    def clear_cache(self, pattern: str = "route:*") -> int:
        """Clear cache entries matching the pattern"""
        if not self.redis:
            log.warning("Redis not available for cache clearing")
            return 0
            
        try:
            keys = self.redis.keys(pattern)
            if keys:
                deleted = self.redis.delete(*keys)
                log.info(f"Cleared {deleted} cache entries matching '{pattern}'")
                return deleted
            else:
                log.info(f"No cache entries found matching '{pattern}'")
                return 0
        except Exception as e:
            log.error(f"Error clearing cache: {e}")
            return 0

    # For testing
    def get_cache_info(self) -> dict:
        """Get information about cached routes"""
        if not self.redis:
            return {"status": "Redis not available"}
            
        try:
            keys = self.redis.keys("route:*")
            cache_info = {
                "total_cached_routes": len(keys),
                "redis_memory_usage": self.redis.info().get('used_memory_human', 'N/A'),
                "cache_ttl_seconds": self.cache_ttl,
                "redis_connected": True
            }
            
            # Get TTL for some sample keys
            if keys:
                sample_ttls = []
                for key in keys[:5]:  # Check first 5 keys
                    ttl = self.redis.ttl(key)
                    if ttl > 0:
                        sample_ttls.append(ttl)
                cache_info["sample_ttls"] = sample_ttls
                
            return cache_info
        except Exception as e:
            log.error(f"Error getting cache info: {e}")
            return {"error": str(e), "redis_connected": False}
    
    def is_available(self) -> bool:
        """Check if Redis cache is available"""
        return self.redis is not None
    
    def health_check(self) -> dict:
        """Perform a health check on the cache"""
        if not self.redis:
            return {"healthy": False, "reason": "Redis not connected"}
            
        try:
            # Simple ping test
            self.redis.ping()
            return {"healthy": True, "cache_ttl": self.cache_ttl}
        except Exception as e:
            log.error(f"Redis health check failed: {e}")
            return {"healthy": False, "reason": str(e)}
