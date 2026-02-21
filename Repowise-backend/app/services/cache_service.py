"""
Cache Service - High-Performance Response Caching
Provides intelligent caching for RAG queries to reduce latency and API costs

Expected Performance:
- Cache Hit: ~50-70% of queries
- Speed Improvement: 10-50x faster (0.1s vs 1-5s)
- Cost Reduction: ~60% fewer LLM API calls
"""

from typing import Optional, Dict, Any
import redis
import json
import hashlib
import logging
from datetime import datetime

logger = logging.getLogger(__name__)


class CacheService:
    """
    Intelligent caching service for RAG responses

    Features:
    - Hash-based exact matching
    - Repository-scoped caching
    - Automatic expiration (TTL)
    - Cache statistics
    - Smart invalidation
    """

    def __init__(
            self,
            redis_url: str = "redis://localhost:6379",
            default_ttl: int = 3600  # 1 hour default
    ):
        """
        Initialize cache service

        Args:
            redis_url: Redis connection URL
            default_ttl: Default cache TTL in seconds (1 hour)
        """
        try:
            self.redis_client = redis.from_url(
                redis_url,
                decode_responses=True
            )
            # Test connection
            self.redis_client.ping()
            logger.info(f"✅ Cache Service connected to Redis at {redis_url}")
            self.connected = True
        except Exception as e:
            logger.error(f"❌ Redis connection failed: {e}")
            logger.warning("⚠️ Cache disabled - all queries will be fresh")
            self.redis_client = None
            self.connected = False

        self.default_ttl = default_ttl

        # Statistics
        self.stats = {
            "hits": 0,
            "misses": 0,
            "sets": 0,
            "errors": 0
        }

    def _generate_cache_key(
            self,
            repo_name: str,
            question: str,
            **kwargs
    ) -> str:
        """
        Generate unique cache key for query

        Args:
            repo_name: Repository name
            question: User question
            **kwargs: Additional parameters (n_results, use_graph, etc.)

        Returns:
            Cache key string
        """
        # Create deterministic hash from query parameters
        cache_data = {
            "repo": repo_name.lower(),
            "question": question.lower().strip(),
            **kwargs
        }

        # Sort dict for consistency
        cache_str = json.dumps(cache_data, sort_keys=True)

        # Generate hash
        cache_hash = hashlib.sha256(cache_str.encode()).hexdigest()[:16]

        # Format: cache:repo:hash
        return f"cache:{repo_name.lower()}:{cache_hash}"

    def get(
            self,
            repo_name: str,
            question: str,
            **kwargs
    ) -> Optional[Dict[str, Any]]:
        """
        Get cached response

        Args:
            repo_name: Repository name
            question: User question
            **kwargs: Additional query parameters

        Returns:
            Cached response dict or None if not found
        """
        if not self.connected:
            return None

        try:
            key = self._generate_cache_key(repo_name, question, **kwargs)

            # Get from Redis
            cached_data = self.redis_client.get(key)

            if cached_data:
                # Cache hit!
                self.stats["hits"] += 1

                # Parse JSON
                result = json.loads(cached_data)

                # Add cache metadata
                result["cached"] = True
                result["cache_key"] = key

                logger.info(f"💚 Cache HIT: {key[:32]}... (repo: {repo_name})")
                return result
            else:
                # Cache miss
                self.stats["misses"] += 1
                logger.info(f"💛 Cache MISS: {key[:32]}... (repo: {repo_name})")
                return None

        except Exception as e:
            self.stats["errors"] += 1
            logger.error(f"Cache get error: {e}")
            return None

    def set(
            self,
            repo_name: str,
            question: str,
            response: Dict[str, Any],
            ttl: Optional[int] = None,
            **kwargs
    ):
        """
        Cache a response

        Args:
            repo_name: Repository name
            question: User question
            response: Response to cache
            ttl: Cache TTL in seconds (default: 1 hour)
            **kwargs: Additional query parameters
        """
        if not self.connected:
            return

        try:
            key = self._generate_cache_key(repo_name, question, **kwargs)
            ttl = ttl or self.default_ttl

            # Prepare cache data
            cache_data = {
                **response,
                "cached_at": datetime.now().isoformat(),
                "ttl": ttl
            }

            # Remove non-serializable fields
            cache_data.pop("cached", None)
            cache_data.pop("cache_key", None)

            # Store in Redis with TTL
            self.redis_client.setex(
                key,
                ttl,
                json.dumps(cache_data)
            )

            self.stats["sets"] += 1
            logger.info(f"💾 Cache SET: {key[:32]}... (TTL: {ttl}s, repo: {repo_name})")

        except Exception as e:
            self.stats["errors"] += 1
            logger.error(f"Cache set error: {e}")

    def invalidate_repository(self, repo_name: str) -> int:
        """
        Invalidate all cache entries for a repository

        Useful when repository is re-indexed

        Args:
            repo_name: Repository name

        Returns:
            Number of keys deleted
        """
        if not self.connected:
            return 0

        try:
            pattern = f"cache:{repo_name.lower()}:*"

            # Find all matching keys
            keys = list(self.redis_client.scan_iter(pattern))

            if keys:
                # Delete all
                deleted = self.redis_client.delete(*keys)
                logger.info(f"🗑️ Cache invalidated for {repo_name}: {deleted} keys deleted")
                return deleted

            return 0

        except Exception as e:
            logger.error(f"Cache invalidation error: {e}")
            return 0

    def invalidate_all(self) -> int:
        """
        Clear entire cache

        Returns:
            Number of keys deleted
        """
        if not self.connected:
            return 0

        try:
            pattern = "cache:*"
            keys = list(self.redis_client.scan_iter(pattern))

            if keys:
                deleted = self.redis_client.delete(*keys)
                logger.info(f"🗑️ Cache cleared: {deleted} keys deleted")

                # Reset stats
                self.stats = {
                    "hits": 0,
                    "misses": 0,
                    "sets": 0,
                    "errors": 0
                }

                return deleted

            return 0

        except Exception as e:
            logger.error(f"Cache clear error: {e}")
            return 0

    def get_stats(self) -> Dict[str, Any]:
        """
        Get cache statistics

        Returns:
            Dictionary with cache stats
        """
        total_requests = self.stats["hits"] + self.stats["misses"]
        hit_rate = (self.stats["hits"] / total_requests * 100) if total_requests > 0 else 0

        try:
            if self.connected:
                # Count cache keys
                cache_keys = list(self.redis_client.scan_iter("cache:*", count=1000))
                total_cached = len(cache_keys)

                # Get memory usage
                info = self.redis_client.info('memory')
                memory_used = info.get('used_memory_human', 'N/A')
            else:
                total_cached = 0
                memory_used = 'N/A'

            return {
                "connected": self.connected,
                "hits": self.stats["hits"],
                "misses": self.stats["misses"],
                "sets": self.stats["sets"],
                "errors": self.stats["errors"],
                "total_requests": total_requests,
                "hit_rate": f"{hit_rate:.1f}%",
                "total_cached": total_cached,
                "memory_used": memory_used,
                "default_ttl": f"{self.default_ttl}s"
            }

        except Exception as e:
            logger.error(f"Stats error: {e}")
            return {
                "connected": self.connected,
                "error": str(e)
            }

    def get_repository_stats(self, repo_name: str) -> Dict[str, Any]:
        """
        Get cache statistics for specific repository

        Args:
            repo_name: Repository name

        Returns:
            Dictionary with repo-specific stats
        """
        if not self.connected:
            return {
                "repository": repo_name,
                "connected": False,
                "cached_queries": 0
            }

        try:
            pattern = f"cache:{repo_name.lower()}:*"
            keys = list(self.redis_client.scan_iter(pattern))

            # Get TTL info for first few keys
            ttls = []
            for key in keys[:10]:
                ttl = self.redis_client.ttl(key)
                if ttl > 0:
                    ttls.append(ttl)

            avg_ttl = sum(ttls) / len(ttls) if ttls else 0

            return {
                "repository": repo_name,
                "connected": True,
                "cached_queries": len(keys),
                "average_ttl_remaining": f"{int(avg_ttl)}s" if avg_ttl > 0 else "N/A"
            }

        except Exception as e:
            logger.error(f"Repository stats error: {e}")
            return {
                "repository": repo_name,
                "error": str(e)
            }


# ============================================================================
# SINGLETON INSTANCE
# ============================================================================

_cache_service: Optional[CacheService] = None


def get_cache_service() -> CacheService:
    """
    Get or create cache service singleton

    Returns:
        CacheService instance
    """
    global _cache_service

    if _cache_service is None:
        _cache_service = CacheService()

    return _cache_service


# Export singleton instance
cache_service = get_cache_service()