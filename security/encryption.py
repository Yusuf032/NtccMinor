from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
import base64
import os
from typing import Optional
from curabot.logger.log import logger
from dotenv import load_dotenv

# Load the environment variables
load_dotenv()


class EncryptionService:
    """
    AES-256 encryption service for securing sensitive data.

    This service uses the Fernet symmetric encryption algorithm (built on top of AES-128 in CBC mode with a 128-bit
    HMAC using SHA256) to ensure guarantees of confidentiality and integrity.
    
    Features:
    - Automatic key generation (if ENCRYPTION_KEY env var is missing).
    - Deterministic hashing for searchable encrypted fields (e.g., email, CIN).
    - Base64 encoding for safe storage of encrypted binaries.
    
    Environment Variables:
        ENCRYPTION_KEY: Base64-encoded 32-byte key for Fernet.
        EMAIL_SALT: Salt for deterministic email hashing.
        HASH_SALT: Salt for general deterministic hashing.
    """
    
    _key = None
    _cipher = None
    
    @classmethod
    def reset(cls):
        """
        Resets the cached key and cipher instance.
        
        Useful for testing or when the encryption key needs to be rotated at runtime.
        """
        cls._key = None
        cls._cipher = None
    
    @classmethod
    def _get_or_create_key(cls) -> bytes:
        """
        Retrieves the encryption key from environment or generates a new one.
        
        Returns:
            bytes: The 32-byte encryption key (urlsafe base64 encoded).
            
        Raises:
            Exception: If key retrieval or generation fails.
        """
        try:
            # Try to get key from environment
            key_b64 = os.getenv('ENCRYPTION_KEY')
            if key_b64:
                # Return the key as bytes for Fernet (it expects base64 string)
                return key_b64.encode()
            
            # Generate new key if not found
            key = Fernet.generate_key()
            logger("CuraDocs_Doctor_CuraBot", "Encryption", "WARN", "HIGH", "Generated new encryption key - add ENCRYPTION_KEY to .env")
            return key
        except Exception as e:
            logger("CuraDocs_Doctor_CuraBot", "Encryption", "ERROR", "CRITICAL", f"Key generation failed: {str(e)}")
            raise
    
    @classmethod
    def _get_cipher(cls):
        """
        Gets or creates the Fernet cipher instance.
        
        This uses a singleton pattern to reuse the expensive cipher initialization.
        
        Returns:
            Fernet: An initialized Fernet cipher object.
        """
        if cls._cipher is None:
            cls._key = cls._get_or_create_key()
            # Fernet expects the key as string, not bytes
            key_str = cls._key.decode() if isinstance(cls._key, bytes) else cls._key
            cls._cipher = Fernet(key_str)
            logger("CuraDocs_Doctor_CuraBot", "Encryption", "INFO", "null", "EncryptionService initialized")
        return cls._cipher
    
    @staticmethod
    def encrypt_data(data: str) -> str:
        """
        Encrypts a string using AES-256 (Fernet).
        
        Args:
            data (str): The plaintext string to encrypt.
            
        Returns:
            str: The base64-encoded ciphertext. Returns empty string if input is empty.
            
        Raises:
            Exception: If encryption fails.
        """
        try:
            if not data:
                return ""
            cipher = EncryptionService._get_cipher()
            encrypted = cipher.encrypt(data.encode())
            return base64.urlsafe_b64encode(encrypted).decode()
        except Exception as e:
            logger("CuraDocs_Doctor_CuraBot", "Encryption", "ERROR", "CRITICAL", f"Encryption failed: {str(e)}")
            raise
    
    @staticmethod
    def decrypt_data(encrypted_data: str) -> str:
        """
        Decrypts a base64-encoded ciphertext.
        
        Args:
            encrypted_data (str): The ciphertext string to decrypt.
            
        Returns:
            str: The original plaintext string. Returns empty string if input is empty.
            
        Raises:
            Exception: If decryption fails (e.g., invalid key, corrupted data).
        """
        try:
            if not encrypted_data:
                return ""
            cipher = EncryptionService._get_cipher()
            encrypted_bytes = base64.urlsafe_b64decode(encrypted_data.encode())
            decrypted = cipher.decrypt(encrypted_bytes)
            return decrypted.decode()
        except Exception as e:
            logger("CuraDocs_Doctor_CuraBot", "Encryption", "ERROR", "CRITICAL", f"Decryption failed: {str(e)}")
            raise
    
    @staticmethod
    def encrypt_email(email: str) -> str:
        """
        Generates a deterministic hash of an email address for secure searching.
        
        Unlike standard encryption (which produces different outputs for the same input),
        this method uses PBKDF2 to always produce the same hash for the same email + salt.
        
        Args:
            email (str): The email address to hash.
            
        Returns:
            str: The base64-encoded hash.
            
        Raises:
            Exception: If hashing fails.
        """
        try:
            # Use simple hash for deterministic email encryption (for search only)
            salt_source = os.getenv('EMAIL_SALT', 'auth_system_email_salt_2024')
            salt = salt_source.encode()
            
            # Create deterministic hash using PBKDF2
            kdf = PBKDF2HMAC(
                algorithm=hashes.SHA256(),
                length=32,
                salt=salt,
                iterations=100000,
            )
            # Use email as input for deterministic result
            email_hash = kdf.derive(email.lower().encode())
            return base64.urlsafe_b64encode(email_hash).decode()
        except Exception as e:
            logger("CuraDocs_Doctor_CuraBot", "Encryption", "ERROR", "CRITICAL", f"Email encryption failed: {str(e)}")
            raise

    @staticmethod
    def hash_data(data: str) -> str:
        """
        Creates a deterministic hash for any sensitive data field (e.g., CIN).
        
        Used for creating searchable indexes of sensitive data without storing
        the plaintext.
        
        Args:
            data (str): The data to hash.
            
        Returns:
            str: The base64-encoded hash. Returns empty string if input is empty.
            
        Raises:
            Exception: If hashing fails.
        """
        try:
            if not data:
                return ""
            salt_source = os.getenv("HASH_SALT", "connect_hash_salt")
            salt = salt_source.encode()

            kdf = PBKDF2HMAC(
                algorithm=hashes.SHA256(),
                length=32,
                salt=salt,
                iterations=100000,
            )
            data_hash = kdf.derive(data.encode())
            return base64.urlsafe_b64encode(data_hash).decode()
        except Exception as e:
            logger("CuraDocs_Doctor_CuraBot", "Encryption", "ERROR", "CRITICAL", f"Data hashing failed: {str(e)}")
            raise 
# Encryption service instance
encryption_service = EncryptionService()
