import warnings
warnings.filterwarnings('ignore')

import hashlib
from typing import Optional, List, Dict, Any
from pydantic_settings import BaseSettings, SettingsConfigDict
from curabot.logger.log import logger
from curabot.core.circuit_breaker import CircuitBreaker
from curabot.config.database import db_settings
from curabot.security.encryption import EncryptionService
from redisvl.extensions.cache.llm import SemanticCache
from redisvl.utils.vectorize import HFTextVectorizer

# -----------------------------------------------------------------------------
# SEMANTIC CACHE MODULE
# -----------------------------------------------------------------------------
# This module implements a secure, patient-scoped semantic cache for LLM responses.
# It uses Redis Vector Library (redisvl) to store and retrieve semantically similar
# queries to reduce LLM costs and latency.
#
# SECURITY & PRIVACY FEATURES:
# 1. Hashed Prompts: The raw user query is NEVER stored. We store a SHA256 hash.
# 2. Encrypted Responses: LLM responses are encrypted using Fernet before storage.
# 3. Hashed Patient IDs: Patient IDs in metadata are hashed for privacy.
# 4. Patient Scoping: Queries are scoped to specific patients to prevent data leaks.
#
# ARCHITECTURE:
# - Lazy Initialization: Cache connects to Redis only on first use.
# - Circuit Breaker: Prevents cascading failures if Redis is down.
# - Graceful Degradation: If redisvl is missing/fails, the app continues without caching.
# -----------------------------------------------------------------------------

_base_config = SettingsConfigDict(
        env_file="./.env",
        env_ignore_empty=True,
        extra="ignore"
    )

class SemanticCacheSettings(BaseSettings):
    """
    Configuration for Semantic Cache.
    """
    # Name of the index in Redis
    SEMANTIC_CACHE_NAME: str 
    
    # Semantic similarity threshold (0.0 to 1.0). Lower = stricter match.
    # Recommended: 0.15 - 0.20 for high precision.
    SEMANTIC_CACHE_DISTANCE_THRESHOLD: float
    
    # Time-to-live for cache entries in seconds (e.g., 3600 = 1 hour)
    SEMANTIC_CACHE_TTL: int
    
    # Redis database number to use (separate from main app DB)
    SEMANTIC_CACHE_REDIS_DB: int
    
    # Master switch to enable/disable semantic caching
    SEMANTIC_CACHE_ENABLED: bool 
    
    # Flag to indicate if redisvl library is installed
    REDISVL_AVAILABLE: bool
    
    model_config = _base_config

settings = SemanticCacheSettings()

# -----------------------------------------------------------------------------
# GLOBAL STATE & CIRCUIT BREAKER
# -----------------------------------------------------------------------------
# _cache_instance: Singleton instance of the SemanticCache.
# _vectorizer: Standalone vectorizer instance. 
#   NOTE: We need a separate _vectorizer because SemanticCache does not expose 
#   its internal vectorizer publicly, and we need to manually generate embeddings 
#   in the store() function to support our "Hashed Prompt" security design.
_cache_instance: Optional[Any] = None
_vectorizer: Optional[Any] = None

# Circuit Breaker to handle Redis failures gracefully
# Trip after 3 failures, wait 30 seconds before retrying.
_circuit_breaker = CircuitBreaker(failure_threshold=3, timeout=30)


# -----------------------------------------------------------------------------
# SECURITY HELPERS
# -----------------------------------------------------------------------------
def _encrypt(data: str) -> str:
    """Encrypt sensitive data (LLM responses) using project's EncryptionService."""
    return EncryptionService.encrypt_data(data)

def _decrypt(data: str) -> str:
    """Decrypt data retrieved from cache."""
    return EncryptionService.decrypt_data(data)

def _hash(data: str) -> str:
    """Hash data (like Patient IDs) for secure metadata filtering."""
    return EncryptionService.hash_data(data)

def _hash_prompt(prompt: str) -> str:
    """
    Create a SHA256 hash of the query prompt.
    This hash is stored in Redis instead of the raw text query to ensure 
    PII in the query is never persisted in the cache.
    """
    return hashlib.sha256(prompt.encode()).hexdigest()

def _secure_metadata(patient_id: str = None, metadata: dict = None) -> dict:
    """
    Prepare metadata for secure storage.
    - Hashes patient_id
    - Encrypts 'clinical_data' field
    - Hashes 'patient_id' inside metadata dictionary
    - Keeps 'records_used' as raw (non-sensitive)
    """
    secured = {}
    
    if patient_id:
        secured["patient_id"] = _hash(patient_id)
    
    if metadata:
        for key, value in metadata.items():
            if key == "records_used":
                secured[key] = value
            elif key == "clinical_data":
                secured[key] = _encrypt(str(value))
            elif key == "patient_id":
                secured[key] = _hash(str(value))
            else:
                secured[key] = value
    
    return secured


# -----------------------------------------------------------------------------
# CORE CACHE MANAGEMENT
# -----------------------------------------------------------------------------
def get_cache() -> Optional[Any]:
    """
    Get or initialize the SemanticCache singleton.
    
    Returns:
        SemanticCache instance or None if disabled/failed.
    """
    global _cache_instance
    
    if not settings.REDISVL_AVAILABLE:
        return None
    
    if _cache_instance is not None:
        return _cache_instance
    
    if not settings.SEMANTIC_CACHE_ENABLED:
        logger("CuraDocs_Doctor_CuraBot", "SemanticCache", "INFO", "LOW", "Semantic cache disabled")
        return None
    
    try:
        # Construct Redis URL for the specific cache DB
        redis_url = db_settings.REDIS_URL(settings.SEMANTIC_CACHE_REDIS_DB)
        
        logger("CuraDocs_Doctor_CuraBot", "SemanticCache", "INFO", "LOW", 
               f"Initializing Semantic Cache: {settings.SEMANTIC_CACHE_NAME}")
        
        # Initialize SemanticCache with local HFTextVectorizer
        # model="all-MiniLM-L6-v2" provides a good balance of speed and accuracy
        _cache_instance = SemanticCache(
            name=settings.SEMANTIC_CACHE_NAME,
            redis_url=redis_url,
            distance_threshold=settings.SEMANTIC_CACHE_DISTANCE_THRESHOLD,
            ttl=settings.SEMANTIC_CACHE_TTL,
            vectorizer=HFTextVectorizer(model="all-MiniLM-L6-v2"),
        )
        
        logger("CuraDocs_Doctor_CuraBot", "SemanticCache", "INFO", "LOW", "Semantic Cache initialized")
        return _cache_instance
        
    except Exception as e:
        logger("CuraDocs_Doctor_CuraBot", "SemanticCache", "ERROR", "HIGH", f"Init failed: {e}")
        return None


# -----------------------------------------------------------------------------
# PUBLIC API
# -----------------------------------------------------------------------------
def check(query: str, patient_id: str = None) -> Optional[List[Dict]]:
    """
    Check the semantic cache for a similar query.
    
    Args:
        query: The user's raw text query.
        patient_id: Optional context to scope the search (privacy).
    
    Returns:
        List of matching cached results (decrypted) or None.
    """
    if not settings.SEMANTIC_CACHE_ENABLED or not settings.REDISVL_AVAILABLE:
        return None
    
    try:
        cache = get_cache()
        if cache is None:
            return None
        
        # Check cache via circuit breaker.
        # NOTE: cache.check() internally generates the embedding for 'query'
        # and searches the vector index. It does NOT care that the stored 'prompt'
        # field is a hash; it compares vectors.
        result = _circuit_breaker.call_sync(lambda: cache.check(prompt=query))
        
        if not result:
            logger("CuraDocs_Doctor_CuraBot", "SemanticCache", "INFO", "LOW", "Cache MISS")
            return None
        
        # Filter results by hashed patient ID (Enforce Scoping)
        if patient_id:
            patient_hash = _hash(patient_id)
            result = [r for r in result if r.get("metadata", {}).get("patient_id") == patient_hash]
            
            if not result:
                logger("CuraDocs_Doctor_CuraBot", "SemanticCache", "INFO", "LOW", "Cache MISS (scope mismatch)")
                return None
        
        # Decrypt cached responses before returning to application
        for item in result:
            if "response" in item:
                item["response"] = _decrypt(item["response"])
        
        logger("CuraDocs_Doctor_CuraBot", "SemanticCache", "INFO", "LOW", "Cache HIT")
        return result
        
    except Exception as e:
        logger("CuraDocs_Doctor_CuraBot", "SemanticCache", "WARN", "MEDIUM", f"Check error: {e}")
        return None


def store(query: str, response: str, patient_id: str = None, metadata: dict = None) -> bool:
    """
    Securely store a query-response pair in the semantic cache.
    
    CRITICAL SECURITY LOGIC:
    We separate the 'Embedding' from the 'Stored Text'.
    1. We generate the embedding vector from the RAW query (so semantic search works).
    2. We store the HASHED query string as the 'prompt' (so raw PII is never stored).
    
    Args:
        query: Raw user query (used for vector gen, then hashed).
        response: LLM response (encrypted before storage).
        patient_id: Patient context (hashed in metadata).
        metadata: Additional info (e.g., usage stats).
    """
    if not settings.SEMANTIC_CACHE_ENABLED or not settings.REDISVL_AVAILABLE:
        return False
    
    try:
        cache = get_cache()
        if cache is None:
            return False
        
        # 1. Generate embedding vector from RAW query
        # We need our own vectorizer instance because cache.vectorizer is not exposed.
        global _vectorizer
        if _vectorizer is None:
            _vectorizer = HFTextVectorizer(model="all-MiniLM-L6-v2")
        query_vector = _vectorizer.embed(query)
        
        # 2. Hash the prompt for secure storage
        hashed_prompt = _hash_prompt(query)
        
        # 3. Secure the payload (Encrypt response, hash metadata IDs)
        encrypted_response = _encrypt(response)
        secured_metadata = _secure_metadata(patient_id, metadata)
        
        # 4. Store in Redis
        # prompt=hashed_prompt  <- Stores SHA256 (Privacy)
        # vector=query_vector   <- Stores Semantic Meaning (Searchability)
        # response=encrypted... <- Stores Encrypted Data (Security)
        _circuit_breaker.call_sync(lambda: cache.store(
            prompt=hashed_prompt,
            response=encrypted_response,
            vector=query_vector,
            metadata=secured_metadata
        ))
        
        logger("CuraDocs_Doctor_CuraBot", "SemanticCache", "INFO", "LOW", "Stored (prompt hashed)")
        return True
        
    except Exception as e:
        logger("CuraDocs_Doctor_CuraBot", "SemanticCache", "WARN", "MEDIUM", f"Store error: {e}")
        return False


def clear() -> bool:
    """Clear all semantic cache entries from Redis."""
    if not settings.SEMANTIC_CACHE_ENABLED or not settings.REDISVL_AVAILABLE:
        return False
    
    try:
        cache = get_cache()
        if cache is None:
            return False
        
        cache.clear()
        logger("CuraDocs_Doctor_CuraBot", "SemanticCache", "INFO", "MEDIUM", "Cache cleared")
        return True
        
    except Exception as e:
        logger("CuraDocs_Doctor_CuraBot", "SemanticCache", "ERROR", "HIGH", f"Clear failed: {e}")
        return False


async def health() -> Dict[str, Any]:
    """
    Diagnostic health check for the Semantic Cache.
    Returns status, configuration, and circuit breaker state.
    """
    if not settings.REDISVL_AVAILABLE:
        return {"status": "unavailable", "healthy": False, "reason": "redisvl missing"}
    
    if not settings.SEMANTIC_CACHE_ENABLED:
        return {"status": "disabled", "healthy": True}
    
    try:
        cache = get_cache()
        if cache is None:
            return {"status": "initialization_failed", "healthy": False}
        
        return {
            "status": "healthy",
            "healthy": True,
            "config": {
                "name": settings.SEMANTIC_CACHE_NAME,
                "ttl": settings.SEMANTIC_CACHE_TTL,
                "threshold": settings.SEMANTIC_CACHE_DISTANCE_THRESHOLD
            },
            "circuit_breaker": "open" if _circuit_breaker.is_open else "closed",
            "security": ["encrypted_responses", "hashed_patient_ids", "hashed_prompts"]
        }
        
    except Exception as e:
        return {"status": "error", "healthy": False, "error": str(e)}


# -----------------------------------------------------------------------------
# ALIASES (Backward Compatibility)
# -----------------------------------------------------------------------------
check_semantic_cache = check
store_in_semantic_cache = store
clear_semantic_cache = clear
check_semantic_cache_health = health
get_semantic_cache = get_cache
