from redis.asyncio import Redis, ConnectionPool
from redis import Redis as SyncRedis, ConnectionPool as SyncConnectionPool
from typing import Optional, Dict, Any
import json
import asyncio
from curabot.config.database import db_settings
from curabot.logger.log import logger
from curabot.config.bloom import bloom_service
from curabot.security.cache_encryption import CacheEncryptionService
from curabot.core.circuit_breaker import CircuitBreaker

# Global Circuit Breaker for Redis to prevent cascading failures
redis_cb = CircuitBreaker(failure_threshold=5, timeout=10)

# Redis connection pool singleton for thread-safe access
class RedisPoolManager:
    _instance = None
    _pool = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    async def get_pool(self):
        # Check if we need to recreate the pool (different loop or pool doesn't exist)
        current_loop = asyncio.get_running_loop()
        
        # If pool exists but belongs to a closed/different loop, reset it
        if self._pool is not None:
            # Try to check if the pool's loop is consistent with current context
            # redis-py pools are bound to the loop they were created in
            pass
            # However, simpler check: if we are in a new loop, we likely need a new pool
            # We can store the loop ID when creating the pool
            if getattr(self, '_pool_loop', None) != current_loop:
                 logger("CuraDocs_Doctor_CuraBot", "Redis Cache", "INFO", "null", "Detected new event loop, recreating Redis pool")
                 try:
                     await self._pool.disconnect()
                 except:
                     pass
                 self._pool = None

        if self._pool is None:
            self._pool = ConnectionPool(
                host=db_settings.REDIS_HOST,
                port=db_settings.REDIS_PORT,
                db=0,
                decode_responses=True,
                max_connections=20,
                retry_on_timeout=True
            )
            self._pool_loop = current_loop
            logger("CuraDocs_Doctor_CuraBot", "Redis Cache", "INFO", "null", "Redis connection pool initialized")
        return self._pool

_pool_manager = RedisPoolManager()

"""Initialize Redis connection pool"""
async def init_redis_pool():
    await _pool_manager.get_pool()
    logger("CuraDocs_Doctor_CuraBot", "Redis Cache", "INFO", "null", "Redis connection pool ready")

"""Get Redis client from connection pool"""
async def get_redis_client():
    pool = await _pool_manager.get_pool()
    return Redis(connection_pool=pool)

"""Get synchronous Redis client for Celery tasks"""
def get_sync_redis_client():
    return SyncRedis(
        host=db_settings.REDIS_HOST,
        port=db_settings.REDIS_PORT,
        db=0,
        decode_responses=True,
        socket_connect_timeout=5
    )

"""Set encrypted data in Redis cache (Synchronous)"""
def set_profile_data_sync(key: str, ttl: int, profile_data: dict):
    redis_client = get_sync_redis_client()
    try:
        # Encrypt sensitive data before caching
        encrypted_data = CacheEncryptionService.encrypt_cache_data(profile_data)
        # Use circuit breaker
        redis_cb.call_sync(lambda: redis_client.setex(key, ttl, encrypted_data))
        logger("CuraDocs_Doctor_CuraBot", "Redis Cache", "INFO", "null", f"Setting encrypted data (Sync) for key: {key}")
    except Exception as e:
        logger("CuraDocs_Doctor_CuraBot", "Redis Cache", "ERROR", "CRITICAL", f"Redis Sync error: {e}")

"""Get and decrypt data from Redis cache (Synchronous)"""
def get_profile_data_sync(key: str) -> Optional[dict]:
    redis_client = get_sync_redis_client()
    try:
        encrypted_data = redis_cb.call_sync(lambda: redis_client.get(key))
        if encrypted_data:
            decrypted_data = CacheEncryptionService.decrypt_cache_data(encrypted_data)
            logger("CuraDocs_Doctor_CuraBot", "Redis Cache", "INFO", "null", f"Cache hit (Sync) for key: {key}")
            return decrypted_data
        return None
    except Exception as e:
        logger("CuraDocs_Doctor_CuraBot", "Redis Cache", "ERROR", "CRITICAL", f"Redis Sync decryption error: {str(e)}")
        return None

"""Delete data from Redis cache (Synchronous)"""
def delete_profile_data_sync(key: str):
    redis_client = get_sync_redis_client()
    try:
        redis_cb.call_sync(lambda: redis_client.delete(key))
        logger("CuraDocs_Doctor_CuraBot", "Redis Cache", "INFO", "null", f"Deleted data (Sync) for key: {key}")
    except Exception as e:
        logger("CuraDocs_Doctor_CuraBot", "Redis Cache", "ERROR", "ERROR", f"Redis Sync delete error: {str(e)}")
        raise

"""Delete multiple keys from Redis matching a pattern (Synchronous)"""
def delete_keys_by_pattern_sync(pattern: str):
    redis_client = get_sync_redis_client()
    try:
        keys_deleted = 0
        cursor = '0'
        while cursor != 0:
            cursor, keys = redis_cb.call_sync(lambda: redis_client.scan(cursor=cursor, match=pattern, count=100))
            if keys:
                redis_cb.call_sync(lambda: redis_client.delete(*keys))
                keys_deleted += len(keys)
                
        logger("CuraDocs_Doctor_CuraBot", "Redis Cache", "INFO", "null", f"Deleted {keys_deleted} keys matching pattern: {pattern}")
        return keys_deleted
    except Exception as e:
        logger("CuraDocs_Doctor_CuraBot", "Redis Cache", "ERROR", "ERROR", f"Redis Sync pattern delete error: {str(e)}")
        raise

"""Set encrypted data in Redis cache with expiration time"""
async def set_profile_data(key: str, ttl: int, profile_data: dict):
    redis_client = await get_redis_client()
    try:
        # Encrypt sensitive data before caching
        encrypted_data = CacheEncryptionService.encrypt_cache_data(profile_data)
        await redis_cb.call(redis_client.setex, key, ttl, encrypted_data)
        logger("CuraDocs_Doctor_CuraBot", "Redis Cache", "INFO", "null", f"Setting encrypted data for key in cache: {key} with TTL: {ttl}")
    except Exception as e:
        logger("CuraDocs_Doctor_CuraBot", "Redis Cache", "ERROR", "CRITICAL", f"Redis error: {e}")
        raise

"""Get and decrypt data from Redis cache by key"""
async def get_profile_data(key: str) -> Optional[dict]:
    redis_client = await get_redis_client()
    try:
        encrypted_data = await redis_cb.call(redis_client.get, key)
        if encrypted_data:
            # Decrypt cached data
            decrypted_data = CacheEncryptionService.decrypt_cache_data(encrypted_data)
            logger("CuraDocs_Doctor_CuraBot", "Redis Cache", "INFO", "null", f"Cache hit getting encrypted data for key from cache: {key}")
            return decrypted_data
        logger("CuraDocs_Doctor_CuraBot", "Redis Cache", "INFO", "null", f"Cache miss for key: {key} (expected for new data)")
        return None
    except Exception as e:
        logger("CuraDocs_Doctor_CuraBot", "Redis Cache", "ERROR", "CRITICAL", f"Redis decryption error: {str(e)}")
        return None

"""Delete data from Redis cache by key"""
async def delete_profile_data(key: str):
    redis_client = await get_redis_client()
    try:
        await redis_cb.call(redis_client.delete, key)
        logger("CuraDocs_Doctor_CuraBot", "Redis Cache", "INFO", "null", f"Deleted data for key in cache: {key}")
    except Exception as e:
        logger("CuraDocs_Doctor_CuraBot", "Redis Cache", "ERROR", "ERROR", f"Redis error: {str(e)}")
        raise

"""Add JWT token to blacklist with Bloom filter optimization"""
async def add_jti_to_blacklist(jti: str):
    redis_client = await get_redis_client()
    try:
        # Add to both Bloom filter and Redis with TTL (24 hours)
        bloom_service.add_blacklisted_token(jti)
        await redis_cb.call(redis_client.setex, jti, 86400, "blacklisted")
        logger("CuraDocs_Doctor_CuraBot", "Redis Cache", "INFO", "null", f"Token blacklisted with Bloom filter: {jti[:10]}...")
    except Exception as e:
        logger("CuraDocs_Doctor_CuraBot", "Redis Cache", "ERROR", "ERROR", f"Failed to blacklist token: {str(e)}")
        raise

"""Check if JWT token is blacklisted using Bloom filter first"""
async def is_jti_blacklisted(jti: str) -> bool:
    try:
        # Fast Bloom filter check first
        if not bloom_service.is_token_blacklisted(jti):
            # Definitely not blacklisted
            return False
        
        # Bloom filter says "maybe" - check Redis for confirmation
        redis_client = await get_redis_client()
        exists = await redis_cb.call(redis_client.exists, jti)
        result = exists == 1
        if result:
            logger("CuraDocs_Doctor_CuraBot", "Redis Cache", "WARN", "HIGH", f"Confirmed blacklisted token: {jti[:10]}...")
        return result
    except Exception as e:
        logger("CuraDocs_Doctor_CuraBot", "Redis Cache", "ERROR", "CRITICAL", "Token blacklist check failed")
        return False

"""Check Redis connection health status"""
async def check_redis_health():
    redis_client = None
    try:
        redis_client = await get_redis_client()
        await redis_cb.call(redis_client.ping)
        logger("CuraDocs_Doctor_CuraBot", "Redis Cache", "INFO", "null", "Redis connection successful")
        return True
    except Exception as e:
        logger("CuraDocs_Doctor_CuraBot", "Redis Cache", "ERROR", "CRITICAL", f"Redis connection failed: {str(e)}")
        return False

"""Continuously monitor Redis health every 60 seconds"""
async def monitor_redis():
    while True:
        try:
            await check_redis_health()
            await asyncio.sleep(300)
        except Exception as e:
            logger("CuraDocs_Doctor_CuraBot", "Redis Cache", "ERROR", "CRITICAL", f"Redis monitoring error: {str(e)}")
            await asyncio.sleep(300)
# Global task reference to prevent garbage collection
_monitoring_task = None

"""Initialize Redis health monitoring as background task"""
def start_redis_monitoring():
    global _monitoring_task
    if _monitoring_task is None or _monitoring_task.done():
        _monitoring_task = asyncio.create_task(monitor_redis())
        logger("CuraDocs_Doctor_CuraBot", "Redis Cache", "INFO", "null", "Redis monitoring task started")
    return _monitoring_task