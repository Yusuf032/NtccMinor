from langchain_community.chat_message_histories import RedisChatMessageHistory
from langchain_core.messages import BaseMessage, messages_from_dict, message_to_dict
from curabot.security.cache_encryption import CacheEncryptionService
import json
from typing import List
from curabot.logger.log import logger

class EncryptedRedisChatMessageHistory(RedisChatMessageHistory):
    """
    A subclass of RedisChatMessageHistory that encrypts messages before storing
    and decrypts them upon retrieval using CacheEncryptionService.
    """

    def add_message(self, message: BaseMessage) -> None:
        """Append the message to the record in Redis, encrypting it first."""
        try:
            # Convert message to dict
            message_dict = message_to_dict(message)
            
            # Encrypt the entire message dictionary structure
            encrypted_data = CacheEncryptionService.encrypt_cache_data(message_dict)
            
            # Use the parent class's logical append method (if exposed) or direct Redis call
            # RedisChatMessageHistory stores as a list of JSON strings.
            # We store the encrypted string directly.
            self.redis_client.rpush(self.key, encrypted_data)
            
            if self.ttl:
                self.redis_client.expire(self.key, self.ttl)
                
        except Exception as e:
            logger("CuraDocs_Doctor_CuraBot", "EncryptedHistory", "ERROR", "HIGH", f"Failed to add encrypted message: {e}")
            raise

    @property
    def messages(self) -> List[BaseMessage]:
        """Retrieve the messages from Redis, decrypting them first."""
        try:
            _items = self.redis_client.lrange(self.key, 0, -1)
            items = []
            allowed_types = ['human', 'ai', 'system']
            
            for item in _items:
                try:
                    # 'item' is the encrypted string stored in Redis
                    if isinstance(item, bytes):
                        item = item.decode("utf-8")
                    
                    # Decrypt
                    decrypted_dict = CacheEncryptionService.decrypt_cache_data(item)
                    
                    if decrypted_dict and isinstance(decrypted_dict, dict):
                        # C. Add message type validation
                        msg_type = decrypted_dict.get("type", "").lower()
                        if msg_type not in allowed_types:
                             logger("CuraDocs_Doctor_CuraBot", "EncryptedHistory", "WARN", "LOW", f"Skipping invalid message type: {msg_type}")
                             continue

                        items.append(decrypted_dict)
                    else:
                        logger("CuraDocs_Doctor_CuraBot", "EncryptedHistory", "WARN", "MEDIUM", "Skipping un-decryptable or invalid message in history")
                except Exception as inner_e:
                     logger("CuraDocs_Doctor_CuraBot", "EncryptedHistory", "WARN", "MEDIUM", f"Error processing history item: {inner_e}")
                     continue

            # Convert list of dicts back to BaseMessages
            return messages_from_dict(items)
            
        except Exception as e:
            logger("CuraDocs_Doctor_CuraBot", "EncryptedHistory", "ERROR", "HIGH", f"Failed to retrieve/decrypt messages: {e}")
            return []

    def clear(self) -> None:
        """Clear session memory from Redis"""
        try:
            self.redis_client.delete(self.key)
        except Exception as e:
            logger("CuraDocs_Doctor_CuraBot", "EncryptedHistory", "ERROR", "MEDIUM", f"Failed to clear history: {e}")
            raise

    @staticmethod
    def reset_session_history(url: str, session_id: str) -> None:
        """
        Utility to clear history for a specific session.
        Useful when switching patients or starting fresh.
        """
        try:
            # Create a temporary history object just to access the key and delete it
            temp_history = EncryptedRedisChatMessageHistory(session_id=session_id, url=url)
            temp_history.clear()
            logger("CuraDocs_Doctor_CuraBot", "EncryptedHistory", "INFO", "null", f"Session history reset for: {session_id}")
        except Exception as e:
            logger("CuraDocs_Doctor_CuraBot", "EncryptedHistory", "ERROR", "MEDIUM", f"Failed to reset session history: {e}")
            raise
