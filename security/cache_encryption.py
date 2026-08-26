from curabot.security.encryption import EncryptionService
import json
from typing import Any, Dict, Optional
from curabot.logger.log import logger

"""
Redis Cache Encryption Service
Provides AES-256 encryption for all cached data to ensure sensitive information
is protected both at rest (database) and in memory (Redis cache).
"""

class CacheEncryptionService:
    """Service for encrypting/decrypting cache data"""
    
    @staticmethod
    def encrypt_cache_data(data: Any) -> str:
        """Encrypt data before storing in cache"""
        try:
            json_data = json.dumps(data, default=str)
            encrypted_data = EncryptionService.encrypt_data(json_data)
            logger("CuraDocs_Doctor_CuraBot", "Cache Encryption", "INFO", "null", "Data encrypted for cache storage")
            return encrypted_data
        except Exception as e:
            logger("CuraDocs_Doctor_CuraBot", "Cache Encryption", "ERROR", "HIGH", f"Cache encryption failed: {str(e)}")
            raise
    
    @staticmethod
    def decrypt_cache_data(encrypted_data: str) -> Optional[Any]:
        """Decrypt data retrieved from cache"""
        try:
            if not encrypted_data:
                return None
            
            json_data = EncryptionService.decrypt_data(encrypted_data)
            data = json.loads(json_data)
            logger("CuraDocs_Doctor_CuraBot", "Cache Encryption", "INFO", "null", "Cache data decrypted successfully")
            return data
        except Exception as e:
            logger("CuraDocs_Doctor_CuraBot", "Cache Encryption", "ERROR", "HIGH", f"Cache decryption failed: {str(e)}")
            return None
    
    @staticmethod
    def is_encrypted_cache_enabled() -> bool:
        """Check if cache encryption is enabled"""
        return True  # Always enabled for enterprise security
