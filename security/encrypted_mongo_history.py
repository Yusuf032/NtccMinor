from langchain_mongodb import MongoDBChatMessageHistory
from langchain_core.messages import BaseMessage, messages_from_dict, message_to_dict
from curabot.security.cache_encryption import CacheEncryptionService
from curabot.logger.log import logger
from typing import List
from pymongo import MongoClient


class EncryptedMongoDBChatMessageHistory(MongoDBChatMessageHistory):
    """
    Encrypted MongoDB Chat Message History for Long-Term Memory.
    
    Encrypts messages before storing and decrypts upon retrieval.
    Uses CacheEncryptionService for Fernet encryption.
    
    Use Case:
        - Store summarized conversation history for long-term memory
        - HIPAA-compliant storage of medical conversations
        - Permanent storage (no TTL like Redis)
    
    Usage:
        history = EncryptedMongoDBChatMessageHistory(
            connection_string="mongodb://localhost:27017",
            database_name="curabot",
            collection_name="long_memory",
            session_id="doctor_VC6JV7z:patient_OsJOoUZ"
        )
        history.add_user_message("Patient has fever")
        messages = history.messages  # Returns decrypted messages
    """

    def add_message(self, message: BaseMessage) -> None:
        """Encrypt and store message in MongoDB."""
        try:
            # Convert message to dict
            message_dict = message_to_dict(message)
            
            # Encrypt the entire message dictionary
            encrypted_data = CacheEncryptionService.encrypt_cache_data(message_dict)
            
            # Store encrypted string in MongoDB
            self.collection.insert_one({
                "SessionId": self.session_id,
                "History": encrypted_data  # Encrypted string
            })
            
            logger("CuraDocs_Doctor_CuraBot", "EncryptedMongoHistory", "INFO", "LOW",
                   f"Message stored in long-term memory: {self.session_id[:20]}...")
                   
        except Exception as e:
            logger("CuraDocs_Doctor_CuraBot", "EncryptedMongoHistory", "ERROR", "HIGH", 
                   f"Failed to add encrypted message: {e}")
            raise

    @property
    def messages(self) -> List[BaseMessage]:
        """Retrieve and decrypt messages from MongoDB."""
        try:
            cursor = self.collection.find({"SessionId": self.session_id})
            items = []
            allowed_types = ['human', 'ai', 'system']
            
            for doc in cursor:
                try:
                    encrypted_data = doc.get("History", "")
                    
                    if not encrypted_data:
                        continue
                    
                    # Decrypt
                    decrypted_dict = CacheEncryptionService.decrypt_cache_data(encrypted_data)
                    
                    if decrypted_dict and isinstance(decrypted_dict, dict):
                        # Validate message type
                        msg_type = decrypted_dict.get("type", "").lower()
                        if msg_type not in allowed_types:
                            logger("CuraDocs_Doctor_CuraBot", "EncryptedMongoHistory", "WARN", "LOW", 
                                   f"Skipping invalid message type: {msg_type}")
                            continue
                        
                        items.append(decrypted_dict)
                    else:
                        logger("CuraDocs_Doctor_CuraBot", "EncryptedMongoHistory", "WARN", "MEDIUM", 
                               "Skipping un-decryptable message")
                               
                except Exception as inner_e:
                    logger("CuraDocs_Doctor_CuraBot", "EncryptedMongoHistory", "WARN", "MEDIUM", 
                           f"Error processing history item: {inner_e}")
                    continue
            
            # Convert list of dicts back to BaseMessages
            return messages_from_dict(items)
            
        except Exception as e:
            logger("CuraDocs_Doctor_CuraBot", "EncryptedMongoHistory", "ERROR", "HIGH", 
                   f"Failed to retrieve/decrypt messages: {e}")
            return []

    def clear(self) -> None:
        """Clear all messages for this session from MongoDB."""
        try:
            result = self.collection.delete_many({"SessionId": self.session_id})
            logger("CuraDocs_Doctor_CuraBot", "EncryptedMongoHistory", "INFO", "LOW",
                   f"Cleared {result.deleted_count} messages for session: {self.session_id[:20]}...")
        except Exception as e:
            logger("CuraDocs_Doctor_CuraBot", "EncryptedMongoHistory", "ERROR", "MEDIUM", 
                   f"Failed to clear history: {e}")
            raise
