from pydantic import BaseModel, Field
from typing import Optional
import json
from curabot.security.encryption import EncryptionService
from curabot.logger.log import logger


class Encrypted_BankingRecord(BaseModel):
    """
    Represents a fully encrypted banking record for secure storage.
    
    All personal, account, and transaction data is encrypted using symmetric encryption (AES-256 via Fernet).
    Searchable identifiers (customer_id, account_id, txn_id) are stored as deterministic hashes (SHA-256)
    to allow lookups without exposing the raw identifier.
    
    PAN numbers are encrypted AND masked — the masked version (e.g., XXXXX1234F) is stored
    alongside the encrypted full PAN for display purposes.
    
    Encryption Pattern (mirrors Encrypted_Prescription from healthcare):
    - Nested objects (customer_data, account_data, transaction_data) → JSON serialized → AES encrypted
    - Scalar identifiers (customer_id, account_id, txn_id) → AES encrypted individually
    - Search keys (customer_id, account_id, txn_id) → SHA-256 deterministic hash
    """
    # Encrypted data fields
    customer_id_encrypted: str = Field(..., description="AES-encrypted Customer ID (CIN)")
    customer_data_encrypted: str = Field(..., description="AES-encrypted JSON blob of customer profile")
    account_data_encrypted: str = Field(..., description="AES-encrypted JSON blob of account details")
    transaction_data_encrypted: str = Field(..., description="AES-encrypted JSON blob of transaction details")
    summary_encrypted: str = Field(..., description="AES-encrypted summary for LLM context")
    pan_masked: str = Field(default="", description="Masked PAN number for display (e.g., XXXXX1234F)")
    
    # Deterministic search hashes (SHA-256 via PBKDF2)
    customer_id_search_hash: str = Field(..., description="SHA-256 hash of customer_id for secure lookup")
    account_id_search_hash: str = Field(default=None, description="SHA-256 hash of account_id for secure lookup")
    txn_id_search_hash: str = Field(default=None, description="SHA-256 hash of txn_id for secure lookup")

    class Config:
        extra = "allow"

    @staticmethod
    def _mask_pan(pan: str) -> str:
        """
        Mask PAN number for display: show only last 5 characters.
        Example: ABCDE1234F → XXXXX1234F
        """
        if not pan or len(pan) < 5:
            return "XXXX" + pan[-1] if pan else ""
        return "X" * (len(pan) - 5) + pan[-5:]

    @classmethod
    def encrypt_record(cls, record_data: dict):
        """
        Create encrypted banking record from plain record data.
        
        This method handles:
        1. JSON serialization of nested fields (customer_data, account_data, transaction_data).
        2. AES Encryption of all content fields.
        3. SHA-256 Hashing of search fields (customer_id, account_id, txn_id) for indexing.
        4. PAN masking for safe display.
        
        Args:
            record_data (dict): Plain dictionary containing banking record data.
            
        Returns:
            Encrypted_BankingRecord: An instance of the model with encrypted data.
        """
        try:
            customer_data = record_data.get("customer_data", {})
            account_data = record_data.get("account_data", {})
            transaction_data = record_data.get("transaction_data", {})
            
            # Extract identifiers for hashing
            customer_id = record_data.get("customer_id", "")
            account_id = account_data.get("account_id", "")
            txn_id = transaction_data.get("txn_id", "")
            pan_number = customer_data.get("pan_number", "")
            
            # Create deterministic search hashes
            customer_id_hash = EncryptionService.hash_data(customer_id)
            account_id_hash = EncryptionService.hash_data(account_id)
            txn_id_hash = EncryptionService.hash_data(txn_id)
            
            # Mask PAN before encryption (store masked version for display)
            masked_pan = cls._mask_pan(pan_number)
            
            return cls(
                customer_id_encrypted=EncryptionService.encrypt_data(customer_id),
                customer_data_encrypted=EncryptionService.encrypt_data(json.dumps(customer_data)),
                account_data_encrypted=EncryptionService.encrypt_data(json.dumps(account_data)),
                transaction_data_encrypted=EncryptionService.encrypt_data(json.dumps(transaction_data)),
                summary_encrypted=EncryptionService.encrypt_data(json.dumps(record_data.get("summary", {}))),
                pan_masked=masked_pan,
                customer_id_search_hash=customer_id_hash,
                account_id_search_hash=account_id_hash,
                txn_id_search_hash=txn_id_hash,
            )
        except Exception as e:
            logger("SecureWealth_Banking", "Encrypted_BankingRecord", "ERROR", "CRITICAL", f"Encryption failed: {str(e)}")
            raise

    def decrypt_record(self) -> dict:
        """
        Convert encrypted banking record to plain data.
        
        Mirrors the decrypt_user pattern from Encrypted_Prescription.
        Falls back to plain field values if decryption fails (backward compatibility).
        """
        def get_value(encrypted_field_name, plain_field_name, cast_type=str):
            encrypted_val = getattr(self, encrypted_field_name, None)
            if encrypted_val:
                try:
                    decrypted = EncryptionService.decrypt_data(encrypted_val)
                    if cast_type == int:
                        return int(decrypted)
                    elif cast_type == float:
                        return float(decrypted)
                    elif cast_type == bool:
                        return decrypted.lower() == 'true'
                    return decrypted
                except Exception:
                    pass
            return getattr(self, plain_field_name, None)

        def get_json_value(encrypted_field_name, plain_field_name):
            encrypted_val = getattr(self, encrypted_field_name, None)
            if isinstance(encrypted_val, str):
                try:
                    decrypted_json = EncryptionService.decrypt_data(encrypted_val)
                    return json.loads(decrypted_json)
                except Exception:
                    pass
            return getattr(self, plain_field_name, {})

        return {
            "customer_id": get_value("customer_id_encrypted", "customer_id"),
            "customer_data": get_json_value("customer_data_encrypted", "customer_data"),
            "account_data": get_json_value("account_data_encrypted", "account_data"),
            "transaction_data": get_json_value("transaction_data_encrypted", "transaction_data"),
            "summary": get_value("summary_encrypted", "summary"),
            "pan_masked": self.pan_masked,
            "customer_id_search_hash": self.customer_id_search_hash,
            "account_id_search_hash": self.account_id_search_hash,
            "txn_id_search_hash": self.txn_id_search_hash,
        }

    def to_dict(self) -> dict:
        """Convert to dictionary for MongoDB storage"""
        return self.dict(exclude_none=True)
