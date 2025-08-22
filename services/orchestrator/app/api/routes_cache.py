"""
Cache Management API Router
============================

Provides endpoints for cache statistics, management, and monitoring.
Integrates with the existing prompt-response agent Redis cache.
"""

import json
import time
from typing import Dict, Any, Optional
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel

# Import the existing cache system (prompt-response agent cache)
from ..services.Caching.cache import RedisCache, settings
from ..services.Caching.settings import CacheConfig


router = APIRouter(prefix="/api/v1/cache", tags=["cache"])


class CacheStatsResponse(BaseModel):
    """Response model for cache statistics"""
    total_entries: int
    hit_rate: float
    memory_usage: str
    cache_enabled: bool
    ttl_seconds: int
    similarity_threshold: float
    semantic_cache_enabled: bool


class CacheEntry(BaseModel):
    """Individual cache entry model"""
    key: str
    session_id: Optional[str]
    has_vector: bool
    created_at: Optional[float]
    last_accessed: Optional[float]
    prompt: Optional[str]
    response: Optional[str]
    label: Optional[str]


def get_cache() -> RedisCache:
    """Dependency to get cache instance"""
    try:
        cache = RedisCache()
        cache.load_config()  # Load persisted configuration
        return cache
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Cache service initialization failed: {str(e)}")


@router.get("/stats", response_model=CacheStatsResponse)
async def get_cache_statistics(cache: RedisCache = Depends(get_cache)):
    """
    Get comprehensive cache statistics including hit rates and memory usage.
    
    Returns:
        CacheStatsResponse: Cache statistics and configuration
    """
    try:
        # Test cache connection
        if not cache.ping():
            raise HTTPException(status_code=503, detail="Cache service unavailable")
        
        # Get all cache entries to calculate statistics
        try:
            entries = cache.list_keys()
            total_entries = len(entries)
        except Exception as e:
            total_entries = 0
            entries = []
        
        # Calculate hit rate from Prometheus metrics (if available)
        # For now, we'll use a basic calculation based on metadata
        hit_rate = 0.0
        total_accesses = 0
        cache_hits = 0
        
        for entry in entries:
            if isinstance(entry, dict) and 'last_accessed' in entry and 'created_at' in entry:
                # If last_accessed > created_at, it means cache was hit
                if entry.get('last_accessed', 0) > entry.get('created_at', 0):
                    cache_hits += 1
                total_accesses += 1
        
        if total_accesses > 0:
            hit_rate = cache_hits / total_accesses
        
        # Get memory usage info from Redis
        memory_usage = "unknown"
        try:
            info = cache.client.info("memory")
            used_memory = info.get("used_memory_human", "unknown")
            memory_usage = used_memory
        except Exception:
            memory_usage = "unavailable"
        
        return CacheStatsResponse(
            total_entries=total_entries,
            hit_rate=hit_rate,
            memory_usage=memory_usage,
            cache_enabled=settings.ENABLED,
            ttl_seconds=settings.CACHE_TTL,
            similarity_threshold=settings.SIMILARITY_THRESHOLD,
            semantic_cache_enabled=settings.USE_SEMANTIC_CACHE
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get cache statistics: {str(e)}")


@router.get("/entries")
async def get_cache_entries(
    limit: int = 100,
    offset: int = 0,
    cache: RedisCache = Depends(get_cache)
):
    """
    Get paginated list of cache entries with metadata.
    
    Args:
        limit: Maximum number of entries to return (default: 100)
        offset: Number of entries to skip (default: 0)
        
    Returns:
        List of cache entries with metadata
    """
    try:
        if not cache.ping():
            raise HTTPException(status_code=503, detail="Cache service unavailable")
        
        # Get all records from cache
        records = cache.export_records()
        
        # Apply pagination
        paginated_records = records[offset:offset + limit]
        
        # Convert to response format
        entries = []
        for record in paginated_records:
            entry = CacheEntry(
                key=record.get("key", ""),
                session_id=record.get("session_id"),
                has_vector=record.get("has_vector", False),
                created_at=record.get("created_at"),
                last_accessed=record.get("last_accessed"),
                prompt=record.get("prompt"),
                response=record.get("response"),
                label=record.get("label")
            )
            entries.append(entry)
        
        return {
            "entries": entries,
            "total": len(records),
            "limit": limit,
            "offset": offset,
            "has_more": (offset + limit) < len(records)
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get cache entries: {str(e)}")


@router.post("/clear")
async def clear_cache(cache: RedisCache = Depends(get_cache)):
    """
    Clear all cache entries.
    
    Returns:
        Success message with cleared entry count
    """
    try:
        if not cache.ping():
            raise HTTPException(status_code=503, detail="Cache service unavailable")
        
        # Get count before clearing
        entries = cache.list_keys()
        entry_count = len(entries)
        
        # Clear the cache
        cache.clear()
        
        return {
            "message": "Cache cleared successfully",
            "entries_cleared": entry_count,
            "timestamp": time.time()
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to clear cache: {str(e)}")


@router.get("/config")
async def get_cache_config(cache: RedisCache = Depends(get_cache)):
    """
    Get current cache configuration.
    
    Returns:
        Current cache configuration settings
    """
    try:
        return {
            "enabled": settings.ENABLED,
            "ttl_seconds": settings.CACHE_TTL,
            "similarity_threshold": settings.SIMILARITY_THRESHOLD,
            "semantic_cache_enabled": settings.USE_SEMANTIC_CACHE,
            "redis_host": settings.REDIS_HOST,
            "redis_port": settings.REDIS_PORT,
            "debug_mode": settings.DEBUG
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get cache config: {str(e)}")


@router.put("/config")
async def update_cache_config(
    enabled: Optional[bool] = None,
    ttl_seconds: Optional[int] = None,
    similarity_threshold: Optional[float] = None,
    cache: RedisCache = Depends(get_cache)
):
    """
    Update cache configuration settings.
    
    Args:
        enabled: Enable/disable caching
        ttl_seconds: Cache entry TTL in seconds
        similarity_threshold: Semantic similarity threshold (0.0-1.0)
        
    Returns:
        Updated configuration
    """
    try:
        if not cache.ping():
            raise HTTPException(status_code=503, detail="Cache service unavailable")
        
        # Update settings if provided
        if enabled is not None:
            cache.set_enabled(enabled)
        
        if ttl_seconds is not None:
            if ttl_seconds <= 0:
                raise HTTPException(status_code=400, detail="TTL must be positive")
            cache.set_ttl(ttl_seconds)
        
        if similarity_threshold is not None:
            if not (0.0 <= similarity_threshold <= 1.0):
                raise HTTPException(status_code=400, detail="Similarity threshold must be between 0.0 and 1.0")
            cache.set_similarity_threshold(similarity_threshold)
        
        # Return updated config
        return {
            "message": "Cache configuration updated",
            "config": {
                "enabled": settings.ENABLED,
                "ttl_seconds": settings.CACHE_TTL,
                "similarity_threshold": settings.SIMILARITY_THRESHOLD,
                "semantic_cache_enabled": settings.USE_SEMANTIC_CACHE
            },
            "timestamp": time.time()
        }
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to update cache config: {str(e)}")


@router.get("/health")
async def cache_health_check(cache: RedisCache = Depends(get_cache)):
    """
    Check cache service health and connectivity.
    
    Returns:
        Health status and connectivity information
    """
    try:
        # Test Redis connection
        ping_result = cache.ping()
        
        if ping_result:
            # Get Redis info
            try:
                info = cache.client.info()
                uptime = info.get("uptime_in_seconds", 0)
                connected_clients = info.get("connected_clients", 0)
                used_memory = info.get("used_memory_human", "unknown")
                
                return {
                    "status": "healthy",
                    "redis_connected": True,
                    "uptime_seconds": uptime,
                    "connected_clients": connected_clients,
                    "memory_usage": used_memory,
                    "cache_enabled": settings.ENABLED,
                    "timestamp": time.time()
                }
            except Exception as e:
                return {
                    "status": "degraded",
                    "redis_connected": True,
                    "cache_enabled": settings.ENABLED,
                    "warning": f"Could not get detailed info: {str(e)}",
                    "timestamp": time.time()
                }
        else:
            return {
                "status": "unhealthy",
                "redis_connected": False,
                "cache_enabled": settings.ENABLED,
                "error": "Redis connection failed",
                "timestamp": time.time()
            }
            
    except Exception as e:
        return {
            "status": "error",
            "redis_connected": False,
            "cache_enabled": False,
            "error": str(e),
            "timestamp": time.time()
        }


@router.get("/export")
async def export_cache_data(format: str = "json", cache: RedisCache = Depends(get_cache)):
    """
    Export cache data in specified format.
    
    Args:
        format: Export format ('json' or 'csv')
        
    Returns:
        Cache data in requested format
    """
    try:
        if not cache.ping():
            raise HTTPException(status_code=503, detail="Cache service unavailable")
        
        if format.lower() == "json":
            data = cache.export_json()
            return {
                "format": "json",
                "data": data,
                "entry_count": len(data),
                "exported_at": time.time()
            }
        elif format.lower() == "csv":
            csv_data = cache.export_full_csv()
            return {
                "format": "csv",
                "data": csv_data,
                "exported_at": time.time()
            }
        else:
            raise HTTPException(status_code=400, detail="Unsupported format. Use 'json' or 'csv'")
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to export cache data: {str(e)}")