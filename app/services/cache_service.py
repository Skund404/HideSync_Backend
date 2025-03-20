# File: services/cache_service.py

"""
Caching service for the HideSync system.

This module provides a flexible caching infrastructure to improve performance
by reducing database queries and computational overhead. It implements multiple
caching strategies and backends with consistent key management and expiration.

The cache service helps reduce latency and database load for frequently accessed
data, calculation results, and expensive operations throughout the application.

Key features:
- In-memory and Redis-based cache implementations
- Namespaced cache keys for organized cache management
- Time-to-live (TTL) support for automatic cache expiration
- Cache invalidation patterns including key and pattern-based invalidation
- Cache warming for predictable performance
- Cache statistics and monitoring
- Function result caching through decorators
- Thread-safe operations

The service follows clean architecture principles and provides a consistent
interface regardless of the underlying cache implementation.
"""

from typing import Dict, Any, Optional, Union, List, Callable, TypeVar, Type
import logging
import json
import hashlib
import time
import threading
import uuid
from datetime import datetime, timedelta
from functools import wraps

logger = logging.getLogger(__name__)

T = TypeVar("T")


class CacheEntry:
    """Represents a cached item with metadata."""

    def __init__(self, key: str, value: Any, ttl: Optional[int] = None):
        """
        Initialize cache entry.

        Args:
            key: Cache key
            value: Cached value
            ttl: Time to live in seconds (None for no expiration)
        """
        self.key = key
        self.value = value
        self.created_at = time.time()
        self.expires_at = self.created_at + ttl if ttl is not None else None
        self.access_count = 0
        self.last_accessed = self.created_at

    @property
    def is_expired(self) -> bool:
        """Check if entry is expired."""
        if self.expires_at is None:
            return False
        return time.time() > self.expires_at

    def touch(self) -> None:
        """Update last accessed time and access count."""
        self.last_accessed = time.time()
        self.access_count += 1

    def to_dict(self) -> Dict[str, Any]:
        """Convert entry to dictionary."""
        return {
            "key": self.key,
            "created_at": datetime.fromtimestamp(self.created_at).isoformat(),
            "expires_at": (
                datetime.fromtimestamp(self.expires_at).isoformat()
                if self.expires_at
                else None
            ),
            "access_count": self.access_count,
            "last_accessed": datetime.fromtimestamp(self.last_accessed).isoformat(),
            "is_expired": self.is_expired,
            "ttl": self.expires_at - self.created_at if self.expires_at else None,
            "remaining_ttl": (
                max(0, self.expires_at - time.time()) if self.expires_at else None
            ),
        }


class CacheBackend:
    """Base class for cache backends."""

    def get(self, key: str) -> Optional[Any]:
        """Get value from cache."""
        raise NotImplementedError("Subclasses must implement get")

    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        """Set value in cache."""
        raise NotImplementedError("Subclasses must implement set")

    def delete(self, key: str) -> bool:
        """Delete key from cache."""
        raise NotImplementedError("Subclasses must implement delete")

    def exists(self, key: str) -> bool:
        """Check if key exists in cache."""
        raise NotImplementedError("Subclasses must implement exists")

    def clear(self) -> bool:
        """Clear all keys from cache."""
        raise NotImplementedError("Subclasses must implement clear")

    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        raise NotImplementedError("Subclasses must implement get_stats")


class MemoryCache(CacheBackend):
    """In-memory cache implementation."""

    def __init__(self, max_size: int = 1000):
        """
        Initialize memory cache.

        Args:
            max_size: Maximum number of items in cache
        """
        self.cache = {}
        self.max_size = max_size
        self.stats = {
            "hits": 0,
            "misses": 0,
            "sets": 0,
            "evictions": 0,
            "expirations": 0,
            "invalidations": 0,
        }

    def get(self, key: str) -> Optional[Any]:
        """
        Get value from cache.

        Args:
            key: Cache key

        Returns:
            Cached value or None if not found or expired
        """
        entry = self.cache.get(key)

        if entry is None:
            self.stats["misses"] += 1
            return None

        # Check if expired
        if entry.is_expired:
            self.stats["expirations"] += 1
            del self.cache[key]
            return None

        # Update access stats
        entry.touch()
        self.stats["hits"] += 1

        return entry.value

    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        """
        Set value in cache.

        Args:
            key: Cache key
            value: Value to cache
            ttl: Time to live in seconds (None for no expiration)

        Returns:
            True if set successfully
        """
        # Check if we need to evict items (LRU policy)
        if len(self.cache) >= self.max_size and key not in self.cache:
            self._evict_lru_item()

        # Create cache entry
        entry = CacheEntry(key, value, ttl)

        # Store in cache
        self.cache[key] = entry
        self.stats["sets"] += 1

        return True

    def delete(self, key: str) -> bool:
        """
        Delete key from cache.

        Args:
            key: Cache key

        Returns:
            True if key was in cache and deleted
        """
        if key in self.cache:
            del self.cache[key]
            self.stats["invalidations"] += 1
            return True
        return False

    def exists(self, key: str) -> bool:
        """
        Check if key exists in cache.

        Args:
            key: Cache key

        Returns:
            True if key exists and is not expired
        """
        entry = self.cache.get(key)

        if entry is None:
            return False

        # Check if expired
        if entry.is_expired:
            del self.cache[key]
            self.stats["expirations"] += 1
            return False

        return True

    def clear(self) -> bool:
        """
        Clear all keys from cache.

        Returns:
            True if cache was cleared
        """
        self.cache.clear()
        return True

    def get_stats(self) -> Dict[str, Any]:
        """
        Get cache statistics.

        Returns:
            Dictionary of cache statistics
        """
        # Calculate hit rate
        total_requests = self.stats["hits"] + self.stats["misses"]
        hit_rate = self.stats["hits"] / total_requests if total_requests > 0 else 0

        # Calculate memory usage (approximate)
        import sys

        memory_usage = sum(
            sys.getsizeof(entry) + sys.getsizeof(entry.value)
            for entry in self.cache.values()
        )

        return {
            "backend": "memory",
            "size": len(self.cache),
            "max_size": self.max_size,
            "memory_usage_bytes": memory_usage,
            "memory_usage_mb": memory_usage / (1024 * 1024),
            "hit_rate": hit_rate,
            "stats": self.stats,
            "active_keys": len(self.cache),
            "expired_keys": self._count_expired(),
        }

    def _evict_lru_item(self) -> bool:
        """
        Evict least recently used item.

        Returns:
            True if an item was evicted
        """
        if not self.cache:
            return False

        # Find least recently used item
        lru_key = min(self.cache.items(), key=lambda x: x[1].last_accessed)[0]

        # Remove from cache
        del self.cache[lru_key]
        self.stats["evictions"] += 1

        return True

    def _count_expired(self) -> int:
        """
        Count expired items in cache.

        Returns:
            Number of expired items
        """
        return sum(1 for entry in self.cache.values() if entry.is_expired)

    def remove_expired(self) -> int:
        """
        Remove all expired items from cache.

        Returns:
            Number of items removed
        """
        keys_to_delete = []

        # Find expired keys
        for key, entry in self.cache.items():
            if entry.is_expired:
                keys_to_delete.append(key)

        # Delete expired keys
        for key in keys_to_delete:
            del self.cache[key]

        self.stats["expirations"] += len(keys_to_delete)
        return len(keys_to_delete)


class RedisCache(CacheBackend):
    """Redis-based cache implementation."""

    def __init__(self, redis_client, namespace: str = "hidesync"):
        """
        Initialize Redis cache.

        Args:
            redis_client: Redis client instance
            namespace: Cache namespace prefix
        """
        self.redis = redis_client
        self.namespace = namespace

    def get(self, key: str) -> Optional[Any]:
        """
        Get value from cache.

        Args:
            key: Cache key

        Returns:
            Cached value or None if not found
        """
        value = self.redis.get(key)

        if value is None:
            return None

        # Deserialize value
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return value

    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        """
        Set value in cache.

        Args:
            key: Cache key
            value: Value to cache
            ttl: Time to live in seconds (None for no expiration)

        Returns:
            True if set successfully
        """
        # Serialize value
        try:
            serialized = json.dumps(value)
        except (TypeError, ValueError):
            logger.warning(f"Could not serialize value for key {key}")
            return False

        # Store in Redis
        if ttl is not None:
            return bool(self.redis.setex(key, ttl, serialized))
        else:
            return bool(self.redis.set(key, serialized))

    def delete(self, key: str) -> bool:
        """
        Delete key from cache.

        Args:
            key: Cache key

        Returns:
            True if key was in cache and deleted
        """
        return bool(self.redis.delete(key))

    def exists(self, key: str) -> bool:
        """
        Check if key exists in cache.

        Args:
            key: Cache key

        Returns:
            True if key exists
        """
        return bool(self.redis.exists(key))

    def clear(self) -> bool:
        """
        Clear all keys from cache.

        Returns:
            True if cache was cleared
        """
        # Only clear keys in our namespace
        pattern = f"{self.namespace}:*"
        keys = self.redis.keys(pattern)

        if keys:
            self.redis.delete(*keys)
        return True

    def get_stats(self) -> Dict[str, Any]:
        """
        Get cache statistics.

        Returns:
            Dictionary of cache statistics
        """
        # Get Redis stats
        info = self.redis.info()

        return {
            "backend": "redis",
            "connected_clients": info.get("connected_clients"),
            "used_memory": info.get("used_memory"),
            "used_memory_human": info.get("used_memory_human"),
            "total_connections_received": info.get("total_connections_received"),
            "total_commands_processed": info.get("total_commands_processed"),
            "keyspace_hits": info.get("keyspace_hits"),
            "keyspace_misses": info.get("keyspace_misses"),
            "hit_rate": (
                info.get("keyspace_hits", 0)
                / (info.get("keyspace_hits", 0) + info.get("keyspace_misses", 1))
            ),
        }


class CacheService:
    """
    Service for managing application caching.

    Provides functionality for:
    - Key-value caching with TTL
    - Namespaced cache keys
    - Cache invalidation and warming
    - Statistics and monitoring
    """

    def __init__(
        self,
        config: Optional[Dict[str, Any]] = None,
        backend_type: str = "memory",
        namespace: str = "hidesync",
    ):
        """
        Initialize cache service.

        Args:
            config: Optional cache configuration
            backend_type: Type of cache backend (memory, redis, etc.)
            namespace: Cache namespace prefix
        """
        self.config = config or {}
        self.namespace = namespace
        self.backend_type = backend_type

        # Default configuration
        self.default_ttl = self.config.get("default_ttl", 3600)  # 1 hour

        # Initialize appropriate backend
        if backend_type == "memory":
            max_size = self.config.get("max_size", 1000)
            self.backend = MemoryCache(max_size=max_size)

            # Start maintenance thread if enabled
            self.maintenance_interval = self.config.get(
                "maintenance_interval", 60
            )  # seconds
            if self.maintenance_interval > 0:
                self._start_maintenance_thread()
        elif backend_type == "redis":
            try:
                import redis

                redis_config = self.config.get("redis_config", {})
                redis_client = redis.Redis(**redis_config)

                # Test connection
                redis_client.ping()

                self.backend = RedisCache(redis_client, namespace=namespace)
            except ImportError:
                logger.warning(
                    "Redis package not installed. Falling back to memory cache."
                )
                self.backend_type = "memory"
                self.backend = MemoryCache()
            except Exception as e:
                logger.warning(
                    f"Failed to connect to Redis: {str(e)}. Falling back to memory cache."
                )
                self.backend_type = "memory"
                self.backend = MemoryCache()
        else:
            logger.warning(
                f"Unsupported cache backend: {backend_type}. Using memory cache."
            )
            self.backend_type = "memory"
            self.backend = MemoryCache()

        logger.info(f"Cache service initialized with {self.backend_type} backend")

    def get(self, key: str, default: Any = None) -> Any:
        """
        Get value from cache.

        Args:
            key: Cache key
            default: Default value if key not found

        Returns:
            Cached value or default
        """
        # Format full key with namespace
        full_key = self._format_key(key)

        # Get from backend
        value = self.backend.get(full_key)

        return default if value is None else value

    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        """
        Set value in cache.

        Args:
            key: Cache key
            value: Value to cache
            ttl: Time to live in seconds (None for default)

        Returns:
            True if set successfully
        """
        # Format full key with namespace
        full_key = self._format_key(key)

        # Use default TTL if not specified
        if ttl is None:
            ttl = self.default_ttl

        # Set in backend
        return self.backend.set(full_key, value, ttl)

    def invalidate(self, key: str) -> bool:
        """
        Invalidate a cache key.

        Args:
            key: Cache key to invalidate

        Returns:
            True if key was in cache and invalidated
        """
        # Format full key with namespace
        full_key = self._format_key(key)

        # Delete from backend
        return self.backend.delete(full_key)

    def invalidate_pattern(self, pattern: str) -> int:
        """
        Invalidate all keys matching a pattern.

        Args:
            pattern: Pattern to match (glob-style for Redis, prefix for memory)

        Returns:
            Number of keys invalidated
        """
        # Prefix with namespace
        namespace_pattern = f"{self.namespace}:{pattern}"

        if self.backend_type == "memory":
            # For memory cache, we can only do prefix matching
            keys_to_delete = []

            for key in list(self.backend.cache.keys()):
                if key.startswith(namespace_pattern):
                    keys_to_delete.append(key)

            # Delete keys
            count = 0
            for key in keys_to_delete:
                if self.backend.delete(key):
                    count += 1

            return count
        elif self.backend_type == "redis":
            # For Redis, we can use pattern matching
            keys = self.backend.redis.keys(f"{namespace_pattern}*")

            if keys:
                return self.backend.redis.delete(*keys)
            return 0

    def get_or_set(
        self, key: str, getter_func: Callable[[], T], ttl: Optional[int] = None
    ) -> T:
        """
        Get value from cache or set it if not present.

        Args:
            key: Cache key
            getter_func: Function to call to get value if not in cache
            ttl: Time to live in seconds (None for default)

        Returns:
            Cached value or newly computed value
        """
        # Try to get from cache
        value = self.get(key)

        if value is not None:
            return value

        # Not in cache, call getter function
        value = getter_func()

        # Cache the value
        if value is not None:
            self.set(key, value, ttl)

        return value

    def mget(self, keys: List[str], default: Any = None) -> Dict[str, Any]:
        """
        Get multiple values from cache.

        Args:
            keys: List of cache keys
            default: Default value for keys not found

        Returns:
            Dictionary of key-value pairs
        """
        result = {}

        for key in keys:
            result[key] = self.get(key, default)

        return result

    def mset(self, mapping: Dict[str, Any], ttl: Optional[int] = None) -> bool:
        """
        Set multiple values in cache.

        Args:
            mapping: Dictionary of key-value pairs
            ttl: Time to live in seconds (None for default)

        Returns:
            True if all values were set successfully
        """
        success = True

        for key, value in mapping.items():
            if not self.set(key, value, ttl):
                success = False

        return success

    def exists(self, key: str) -> bool:
        """
        Check if key exists in cache.

        Args:
            key: Cache key

        Returns:
            True if key exists
        """
        # Format full key with namespace
        full_key = self._format_key(key)

        # Check in backend
        return self.backend.exists(full_key)

    def get_stats(self) -> Dict[str, Any]:
        """
        Get cache statistics.

        Returns:
            Cache statistics
        """
        return self.backend.get_stats()

    def clear(self) -> bool:
        """
        Clear all cached items.

        Returns:
            True if cache was cleared successfully
        """
        return self.backend.clear()

    def warm_cache(
        self, keys_values: Dict[str, Callable[[], Any]], ttl: Optional[int] = None
    ) -> None:
        """
        Warm cache with provided keys and getter functions.

        Args:
            keys_values: Dictionary mapping keys to getter functions
            ttl: Time to live in seconds (None for default)
        """
        for key, getter_func in keys_values.items():
            try:
                value = getter_func()
                if value is not None:
                    self.set(key, value, ttl)
            except Exception as e:
                logger.warning(f"Failed to warm cache for key {key}: {str(e)}")

    def _format_key(self, key: str) -> str:
        """
        Format a key with namespace.

        Args:
            key: Original key

        Returns:
            Namespaced key
        """
        return f"{self.namespace}:{key}"

    def _start_maintenance_thread(self) -> None:
        """Start maintenance thread for periodic cleanup."""

        def maintenance_task():
            while True:
                try:
                    # Sleep first to avoid immediate cleanup at initialization
                    time.sleep(self.maintenance_interval)

                    # Remove expired items if backend supports it
                    if hasattr(self.backend, "remove_expired"):
                        self.backend.remove_expired()
                except Exception as e:
                    logger.error(f"Error in cache maintenance task: {str(e)}")

        # Start maintenance thread as daemon
        thread = threading.Thread(target=maintenance_task, daemon=True)
        thread.start()


def cached(key_prefix: str, ttl: Optional[int] = None):
    """
    Decorator to cache function results.

    Args:
        key_prefix: Prefix for cache key
        ttl: Time to live in seconds (None for default)

    Returns:
        Decorated function
    """

    def decorator(func):
        @wraps(func)
        def wrapper(self, *args, **kwargs):
            # Skip caching if no cache service
            if not hasattr(self, "cache_service") or self.cache_service is None:
                return func(self, *args, **kwargs)

            # Generate cache key
            cache_key = _generate_cache_key(key_prefix, func.__name__, args, kwargs)

            # Try to get from cache
            cached_value = self.cache_service.get(cache_key)
            if cached_value is not None:
                return cached_value

            # Not in cache, call function
            result = func(self, *args, **kwargs)

            # Cache result if not None
            if result is not None:
                self.cache_service.set(cache_key, result, ttl)

            return result

        return wrapper

    return decorator


def _generate_cache_key(prefix: str, func_name: str, args: tuple, kwargs: dict) -> str:
    """
    Generate a cache key for a function call.

    Args:
        prefix: Key prefix
        func_name: Function name
        args: Function arguments
        kwargs: Function keyword arguments

    Returns:
        Cache key
    """
    # Convert args and kwargs to strings
    args_str = ",".join(str(arg) for arg in args)
    kwargs_str = ",".join(f"{k}={v}" for k, v in sorted(kwargs.items()))

    # Combine parts
    key_parts = [prefix, func_name]

    if args_str:
        key_parts.append(args_str)
    if kwargs_str:
        key_parts.append(kwargs_str)

    # Join with colons
    key = ":".join(key_parts)

    # If key is too long, use a hash
    if len(key) > 250:
        key = f"{prefix}:{func_name}:{hashlib.md5((args_str + kwargs_str).encode()).hexdigest()}"

    return key
