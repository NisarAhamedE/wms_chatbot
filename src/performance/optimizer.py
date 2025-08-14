"""
Advanced performance optimization system for WMS Chatbot
Provides intelligent caching, query optimization, and resource management
"""

import asyncio
import json
import time
import hashlib
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Union, Callable
from dataclasses import dataclass, asdict
from enum import Enum
import aioredis
import numpy as np
from sqlalchemy import text
from functools import wraps, lru_cache
import pickle
import gzip
from concurrent.futures import ThreadPoolExecutor

from src.core.config import get_settings
from src.database.connection import get_database_manager

logger = logging.getLogger(__name__)

class CacheStrategy(Enum):
    """Cache strategies"""
    LRU = "lru"
    TTL = "ttl"
    LFU = "lfu"
    FIFO = "fifo"

class OptimizationLevel(Enum):
    """Optimization levels"""
    BASIC = "basic"
    STANDARD = "standard"
    AGGRESSIVE = "aggressive"

@dataclass
class CacheEntry:
    """Cache entry with metadata"""
    key: str
    value: Any
    created_at: datetime
    last_accessed: datetime
    access_count: int = 0
    ttl_seconds: Optional[int] = None
    compressed: bool = False
    size_bytes: int = 0

@dataclass
class QueryStats:
    """Query performance statistics"""
    query_hash: str
    query: str
    execution_count: int = 0
    total_execution_time: float = 0.0
    avg_execution_time: float = 0.0
    min_execution_time: float = float('inf')
    max_execution_time: float = 0.0
    last_execution: Optional[datetime] = None
    errors: int = 0

class SmartCache:
    """Intelligent multi-level cache system"""
    
    def __init__(self, strategy: CacheStrategy = CacheStrategy.LRU, max_size: int = 10000):
        self.strategy = strategy
        self.max_size = max_size
        self.cache: Dict[str, CacheEntry] = {}
        self.access_order: List[str] = []
        self.redis_client: Optional[aioredis.Redis] = None
        self.compression_threshold = 1024  # Compress entries > 1KB
        
    async def initialize_redis(self):
        """Initialize Redis connection for distributed caching"""
        try:
            settings = get_settings()
            redis_url = f"redis://:{settings.redis_password}@{settings.redis_host}:{settings.redis_port}/0"
            self.redis_client = await aioredis.from_url(redis_url)
            logger.info("Redis cache initialized")
        except Exception as e:
            logger.warning(f"Redis initialization failed, using memory cache only: {e}")
    
    def _generate_key(self, namespace: str, identifier: str, **kwargs) -> str:
        """Generate cache key with namespace and parameters"""
        key_data = f"{namespace}:{identifier}:{json.dumps(kwargs, sort_keys=True)}"
        return hashlib.sha256(key_data.encode()).hexdigest()
    
    def _compress_value(self, value: Any) -> bytes:
        """Compress value for storage"""
        serialized = pickle.dumps(value)
        return gzip.compress(serialized)
    
    def _decompress_value(self, compressed_data: bytes) -> Any:
        """Decompress value from storage"""
        decompressed = gzip.decompress(compressed_data)
        return pickle.loads(decompressed)
    
    async def get(self, key: str) -> Optional[Any]:
        """Get value from cache"""
        # Try local cache first
        if key in self.cache:
            entry = self.cache[key]
            
            # Check TTL expiration
            if entry.ttl_seconds:
                elapsed = (datetime.utcnow() - entry.created_at).total_seconds()
                if elapsed > entry.ttl_seconds:
                    await self.delete(key)
                    return None
            
            # Update access metadata
            entry.last_accessed = datetime.utcnow()
            entry.access_count += 1
            
            # Update access order for LRU
            if self.strategy == CacheStrategy.LRU:
                self.access_order.remove(key)
                self.access_order.append(key)
            
            return entry.value
        
        # Try Redis if available
        if self.redis_client:
            try:
                cached_data = await self.redis_client.get(key)
                if cached_data:
                    entry_data = json.loads(cached_data.decode())
                    
                    # Check TTL
                    if entry_data.get('ttl_seconds'):
                        elapsed = time.time() - entry_data['created_at']
                        if elapsed > entry_data['ttl_seconds']:
                            await self.redis_client.delete(key)
                            return None
                    
                    # Deserialize value
                    if entry_data.get('compressed'):
                        value = self._decompress_value(entry_data['value'])
                    else:
                        value = entry_data['value']
                    
                    return value
            except Exception as e:
                logger.warning(f"Redis cache get failed: {e}")
        
        return None
    
    async def set(self, key: str, value: Any, ttl_seconds: Optional[int] = None):
        """Set value in cache"""
        current_time = datetime.utcnow()
        
        # Serialize and possibly compress value
        serialized_size = len(pickle.dumps(value))
        should_compress = serialized_size > self.compression_threshold
        
        # Create cache entry
        entry = CacheEntry(
            key=key,
            value=value,
            created_at=current_time,
            last_accessed=current_time,
            access_count=1,
            ttl_seconds=ttl_seconds,
            compressed=should_compress,
            size_bytes=serialized_size
        )
        
        # Store in local cache
        await self._evict_if_needed()
        self.cache[key] = entry
        
        if self.strategy == CacheStrategy.LRU:
            if key in self.access_order:
                self.access_order.remove(key)
            self.access_order.append(key)
        
        # Store in Redis if available
        if self.redis_client:
            try:
                entry_data = {
                    'value': self._compress_value(value) if should_compress else value,
                    'created_at': time.time(),
                    'ttl_seconds': ttl_seconds,
                    'compressed': should_compress
                }
                
                await self.redis_client.set(
                    key, 
                    json.dumps(entry_data, default=str),
                    ex=ttl_seconds if ttl_seconds else None
                )
            except Exception as e:
                logger.warning(f"Redis cache set failed: {e}")
    
    async def delete(self, key: str):
        """Delete key from cache"""
        if key in self.cache:
            del self.cache[key]
            if key in self.access_order:
                self.access_order.remove(key)
        
        if self.redis_client:
            try:
                await self.redis_client.delete(key)
            except Exception as e:
                logger.warning(f"Redis cache delete failed: {e}")
    
    async def clear(self):
        """Clear all cache entries"""
        self.cache.clear()
        self.access_order.clear()
        
        if self.redis_client:
            try:
                await self.redis_client.flushdb()
            except Exception as e:
                logger.warning(f"Redis cache clear failed: {e}")
    
    async def _evict_if_needed(self):
        """Evict entries if cache is full"""
        if len(self.cache) >= self.max_size:
            if self.strategy == CacheStrategy.LRU:
                # Remove least recently used
                lru_key = self.access_order[0]
                await self.delete(lru_key)
            elif self.strategy == CacheStrategy.LFU:
                # Remove least frequently used
                lfu_key = min(self.cache.keys(), key=lambda k: self.cache[k].access_count)
                await self.delete(lfu_key)
            elif self.strategy == CacheStrategy.FIFO:
                # Remove first in
                oldest_key = min(self.cache.keys(), key=lambda k: self.cache[k].created_at)
                await self.delete(oldest_key)
    
    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics"""
        total_size = sum(entry.size_bytes for entry in self.cache.values())
        compressed_count = sum(1 for entry in self.cache.values() if entry.compressed)
        
        return {
            "entries": len(self.cache),
            "max_size": self.max_size,
            "total_size_bytes": total_size,
            "compressed_entries": compressed_count,
            "strategy": self.strategy.value,
            "redis_connected": self.redis_client is not None
        }

class QueryOptimizer:
    """SQL query optimization and performance tracking"""
    
    def __init__(self):
        self.query_stats: Dict[str, QueryStats] = {}
        self.slow_query_threshold = 1.0  # seconds
        self.cache = SmartCache(CacheStrategy.LRU, max_size=1000)
        
    def _get_query_hash(self, query: str) -> str:
        """Generate hash for query caching"""
        normalized_query = query.strip().lower()
        return hashlib.md5(normalized_query.encode()).hexdigest()
    
    async def execute_with_optimization(
        self, 
        session, 
        query: str, 
        params: Dict[str, Any] = None,
        cache_ttl: Optional[int] = None
    ) -> Any:
        """Execute query with optimization and caching"""
        query_hash = self._get_query_hash(query)
        start_time = time.time()
        
        # Try cache first for SELECT queries
        if query.strip().lower().startswith('select') and cache_ttl:
            cache_key = self.cache._generate_key("query", query_hash, params=params or {})
            cached_result = await self.cache.get(cache_key)
            if cached_result is not None:
                logger.debug(f"Query cache hit: {query_hash[:8]}")
                return cached_result
        
        try:
            # Execute query
            if params:
                result = await session.execute(text(query), params)
            else:
                result = await session.execute(text(query))
            
            # Fetch results for SELECT queries
            if query.strip().lower().startswith('select'):
                rows = result.fetchall()
                # Convert to list of dicts for JSON serialization
                result_data = [dict(row) for row in rows]
                
                # Cache results if specified
                if cache_ttl:
                    cache_key = self.cache._generate_key("query", query_hash, params=params or {})
                    await self.cache.set(cache_key, result_data, cache_ttl)
                
                execution_result = result_data
            else:
                execution_result = result.rowcount
            
            # Record successful execution
            execution_time = time.time() - start_time
            await self._record_query_stats(query_hash, query, execution_time, success=True)
            
            return execution_result
            
        except Exception as e:
            execution_time = time.time() - start_time
            await self._record_query_stats(query_hash, query, execution_time, success=False)
            raise e
    
    async def _record_query_stats(
        self, 
        query_hash: str, 
        query: str, 
        execution_time: float, 
        success: bool
    ):
        """Record query performance statistics"""
        if query_hash not in self.query_stats:
            self.query_stats[query_hash] = QueryStats(
                query_hash=query_hash,
                query=query[:500]  # Truncate long queries
            )
        
        stats = self.query_stats[query_hash]
        stats.execution_count += 1
        stats.last_execution = datetime.utcnow()
        
        if success:
            stats.total_execution_time += execution_time
            stats.avg_execution_time = stats.total_execution_time / stats.execution_count
            stats.min_execution_time = min(stats.min_execution_time, execution_time)
            stats.max_execution_time = max(stats.max_execution_time, execution_time)
            
            if execution_time > self.slow_query_threshold:
                logger.warning(f"Slow query detected: {execution_time:.2f}s - {query[:100]}")
        else:
            stats.errors += 1
    
    def get_slow_queries(self) -> List[QueryStats]:
        """Get queries that exceed performance threshold"""
        return [
            stats for stats in self.query_stats.values()
            if stats.avg_execution_time > self.slow_query_threshold
        ]
    
    def get_query_recommendations(self) -> List[str]:
        """Get query optimization recommendations"""
        recommendations = []
        
        for stats in self.query_stats.values():
            query = stats.query.lower()
            
            # Check for missing WHERE clauses in SELECT queries
            if (query.startswith('select') and 
                'where' not in query and 
                stats.avg_execution_time > 0.5):
                recommendations.append(
                    f"Consider adding WHERE clause to query: {stats.query[:50]}..."
                )
            
            # Check for queries without LIMIT
            if (query.startswith('select') and 
                'limit' not in query and 
                stats.avg_execution_time > 1.0):
                recommendations.append(
                    f"Consider adding LIMIT clause to query: {stats.query[:50]}..."
                )
            
            # Check for frequent queries that could benefit from indexes
            if stats.execution_count > 100 and stats.avg_execution_time > 0.1:
                recommendations.append(
                    f"Frequently executed query may benefit from indexing: {stats.query[:50]}..."
                )
        
        return recommendations

class ConnectionPool:
    """Advanced database connection pool with monitoring"""
    
    def __init__(self, min_connections: int = 5, max_connections: int = 20):
        self.min_connections = min_connections
        self.max_connections = max_connections
        self.active_connections = 0
        self.idle_connections = 0
        self.total_requests = 0
        self.failed_requests = 0
        
    def get_stats(self) -> Dict[str, Any]:
        """Get connection pool statistics"""
        return {
            "active_connections": self.active_connections,
            "idle_connections": self.idle_connections,
            "total_requests": self.total_requests,
            "failed_requests": self.failed_requests,
            "success_rate": (
                (self.total_requests - self.failed_requests) / 
                max(self.total_requests, 1) * 100
            )
        }

class PerformanceMiddleware:
    """Performance monitoring middleware"""
    
    def __init__(self):
        self.request_stats = {}
        self.active_requests = 0
        
    async def __call__(self, request, call_next):
        """Process request with performance monitoring"""
        start_time = time.time()
        self.active_requests += 1
        
        try:
            response = await call_next(request)
            execution_time = time.time() - start_time
            
            # Record stats
            endpoint = f"{request.method}:{request.url.path}"
            if endpoint not in self.request_stats:
                self.request_stats[endpoint] = {
                    "count": 0,
                    "total_time": 0.0,
                    "avg_time": 0.0,
                    "min_time": float('inf'),
                    "max_time": 0.0
                }
            
            stats = self.request_stats[endpoint]
            stats["count"] += 1
            stats["total_time"] += execution_time
            stats["avg_time"] = stats["total_time"] / stats["count"]
            stats["min_time"] = min(stats["min_time"], execution_time)
            stats["max_time"] = max(stats["max_time"], execution_time)
            
            # Add performance headers
            response.headers["X-Response-Time"] = f"{execution_time:.3f}s"
            response.headers["X-Active-Requests"] = str(self.active_requests)
            
            return response
            
        finally:
            self.active_requests -= 1
    
    def get_stats(self) -> Dict[str, Any]:
        """Get performance statistics"""
        return {
            "endpoints": self.request_stats,
            "active_requests": self.active_requests
        }

class ResourceMonitor:
    """System resource monitoring and optimization"""
    
    def __init__(self):
        self.cpu_history = []
        self.memory_history = []
        self.disk_history = []
        self.max_history = 1000
        
    async def collect_metrics(self):
        """Collect system resource metrics"""
        try:
            import psutil
            
            # CPU usage
            cpu_percent = psutil.cpu_percent(interval=1)
            self.cpu_history.append({
                "timestamp": time.time(),
                "value": cpu_percent
            })
            
            # Memory usage
            memory = psutil.virtual_memory()
            self.memory_history.append({
                "timestamp": time.time(),
                "value": memory.percent
            })
            
            # Disk usage
            disk = psutil.disk_usage('/')
            disk_percent = (disk.used / disk.total) * 100
            self.disk_history.append({
                "timestamp": time.time(),
                "value": disk_percent
            })
            
            # Trim history
            current_time = time.time()
            hour_ago = current_time - 3600
            
            self.cpu_history = [
                item for item in self.cpu_history 
                if item["timestamp"] > hour_ago
            ]
            self.memory_history = [
                item for item in self.memory_history 
                if item["timestamp"] > hour_ago
            ]
            self.disk_history = [
                item for item in self.disk_history 
                if item["timestamp"] > hour_ago
            ]
            
        except Exception as e:
            logger.error(f"Failed to collect resource metrics: {e}")
    
    def get_resource_recommendations(self) -> List[str]:
        """Get resource optimization recommendations"""
        recommendations = []
        
        if self.cpu_history:
            avg_cpu = np.mean([item["value"] for item in self.cpu_history[-10:]])
            if avg_cpu > 80:
                recommendations.append("High CPU usage detected. Consider scaling up or optimizing queries.")
        
        if self.memory_history:
            avg_memory = np.mean([item["value"] for item in self.memory_history[-10:]])
            if avg_memory > 85:
                recommendations.append("High memory usage detected. Consider increasing memory or optimizing cache.")
        
        if self.disk_history:
            avg_disk = np.mean([item["value"] for item in self.disk_history[-10:]])
            if avg_disk > 85:
                recommendations.append("Low disk space detected. Consider cleanup or adding storage.")
        
        return recommendations

class PerformanceOptimizer:
    """Main performance optimization coordinator"""
    
    def __init__(self, level: OptimizationLevel = OptimizationLevel.STANDARD):
        self.level = level
        self.cache = SmartCache()
        self.query_optimizer = QueryOptimizer()
        self.resource_monitor = ResourceMonitor()
        self.middleware = PerformanceMiddleware()
        self.thread_pool = ThreadPoolExecutor(max_workers=4)
        
    async def initialize(self):
        """Initialize performance optimizer"""
        await self.cache.initialize_redis()
        logger.info(f"Performance optimizer initialized with {self.level.value} level")
    
    def cache_result(self, ttl_seconds: int = 300):
        """Decorator for caching function results"""
        def decorator(func):
            @wraps(func)
            async def wrapper(*args, **kwargs):
                # Generate cache key
                func_name = func.__name__
                cache_key = self.cache._generate_key(
                    "function", func_name, args=args, kwargs=kwargs
                )
                
                # Try cache first
                cached_result = await self.cache.get(cache_key)
                if cached_result is not None:
                    return cached_result
                
                # Execute function
                result = await func(*args, **kwargs)
                
                # Cache result
                await self.cache.set(cache_key, result, ttl_seconds)
                
                return result
            return wrapper
        return decorator
    
    async def optimize_database_query(
        self, 
        session, 
        query: str, 
        params: Dict[str, Any] = None,
        cache_ttl: Optional[int] = None
    ):
        """Execute optimized database query"""
        return await self.query_optimizer.execute_with_optimization(
            session, query, params, cache_ttl
        )
    
    def get_performance_report(self) -> Dict[str, Any]:
        """Generate comprehensive performance report"""
        return {
            "cache_stats": self.cache.get_stats(),
            "slow_queries": len(self.query_optimizer.get_slow_queries()),
            "query_recommendations": self.query_optimizer.get_query_recommendations(),
            "resource_recommendations": self.resource_monitor.get_resource_recommendations(),
            "middleware_stats": self.middleware.get_stats(),
            "optimization_level": self.level.value
        }
    
    async def cleanup(self):
        """Cleanup resources"""
        if self.cache.redis_client:
            await self.cache.redis_client.close()
        self.thread_pool.shutdown(wait=True)

# Global performance optimizer instance
performance_optimizer = PerformanceOptimizer()

async def get_performance_optimizer() -> PerformanceOptimizer:
    """Get performance optimizer instance"""
    return performance_optimizer