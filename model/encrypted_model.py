from pydantic import BaseModel, Field
from typing import List, Optional
import json
from curabot.security.encryption import EncryptionService
from curabot.logger.log import logger


class BasicDetails(BaseModel):
    date: str = Field(..., description="Date of the consultation in YYYY-MM-DD format")
    patient_name: str = Field(..., description="Full name of the patient")
    doctor_name: str = Field(..., description="Full name of the doctor")


class ClinicalDetails(BaseModel):
    clinic_name: str = Field(..., description="Name of the clinic or hospital")
    phone_number: str = Field(..., description="Contact phone number of the clinic or hospital")
    address: str = Field(..., description="Address of the clinic or hospital")


class PatientDetails(BaseModel):
    age: int = Field(..., description="Age of the patient")
    gender: str = Field(..., description="Gender of the patient")
    CIN_1: str = Field(..., description="CIN (unique ID) of the patient")


class Diagnosis(BaseModel):
    symptoms: str = Field(..., description="Symptoms reported by the patient")
    description: str = Field(..., description="Detailed description of the diagnosis")


class DoctorDetails(BaseModel):
    CIN_2: Optional[str] = Field(None, description="CIN (unique ID) of the doctor")


class PrescribedItem(BaseModel):
    name: str = Field(..., description="Name of the prescribed item")
    dosage: str = Field(..., description="Dosage of the prescribed item")
    frequency: str = Field(..., description="Frequency of the prescribed item")
    duration: str = Field(..., description="Duration for which the item is prescribed")


class Encrypted_Prescription(BaseModel):
    """
    Represents a fully encrypted prescription record for secure storage.
    
    All personal and clinical data is encrypted using symmetric encryption (AES-CBC).
    Searchable identifiers (CINs) are stored as deterministic hashes (SHA-256) to allow lookups 
    without exposing the raw identifier.
    """
    CIN_1_encrypted: str = Field(..., description="CIN (unique ID) of the patient")
    CIN_2_encrypted: str = Field(default=None, description="CIN (unique ID) of the doctor")
    basic_details_encrypted: str = Field(..., description="Basic details of the consultation")
    clinical_details_encrypted: str = Field(..., description="Clinical details of the clinic or hospital")
    patient_details_encrypted: str = Field(..., description="Details of the patient")
    diagnosis_encrypted: str = Field(..., description="Diagnosis details including symptoms and description")
    prescribed_items_encrypted: str = Field(..., description="List of prescribed items")
    summary_encrypted: str = Field(..., description="Summary of the consultation")
    CIN_1_search_hash: str = Field(..., description="Hash of the CIN (unique ID) of the patient")
    CIN_2_search_hash: str = Field(default=None, description="Hash of the CIN (unique ID) of the doctor")

    class Config:
        extra = "allow"

    @classmethod
    def encrypt_user(cls, user_data: dict):
        """
        Create encrypted user from plain user data.
        
        This method handles:
        1. JSON serialization of nested fields (prescriptions, details).
        2. AES Encryption of all content fields.
        3. SHA-256 Hashing of search fields (CINs) for indexing.
        
        Args:
            user_data (dict): Plain dictionary containing prescription data.
            
        Returns:
            Encrypted_Prescription: An instance of the model with encrypted data.
        """
        try:
            email = user_data.get("email", "")
            prescribed_items = user_data.get("prescribed_items", [])
            prescribed_items_json = json.dumps(prescribed_items)
            cin1_hash = EncryptionService.hash_data(user_data.get("CIN_1", ""))
            cin2_hash = EncryptionService.hash_data(user_data.get("CIN_2", ""))

            return cls(
                CIN_1_encrypted=EncryptionService.encrypt_data(user_data.get("CIN_1", "")),
                CIN_2_encrypted=EncryptionService.encrypt_data(user_data.get("CIN_2", "")),
                basic_details_encrypted=EncryptionService.encrypt_data(json.dumps(user_data.get("basic_details", {}))),
                patient_details_encrypted=EncryptionService.encrypt_data(json.dumps(user_data.get("patient_details", {}))),
                diagnosis_encrypted=EncryptionService.encrypt_data(json.dumps(user_data.get("diagnosis", {}))),
                clinical_details_encrypted=EncryptionService.encrypt_data(json.dumps(user_data.get("clinical_details", {}))),
                prescribed_items_encrypted=EncryptionService.encrypt_data(prescribed_items_json),
                summary_encrypted=EncryptionService.encrypt_data(json.dumps(user_data.get("summary", {}))),
                CIN_1_search_hash=cin1_hash,
                CIN_2_search_hash=cin2_hash,
            )
        except Exception as e:
            logger("CuraDocs_Doctor_CuraBot", "Encrypted_Prescription", "ERROR", "CRITICAL", f"Encryption failed: {str(e)}")
            raise

    def decrypt_user(self) -> dict:
        """Convert encrypted user to plain user data"""
        # Helper to safely decrypt and cast
        def get_value(encrypted_field_name, plain_field_name, cast_type=str):
            # 1. Try encrypted field
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
            
            # 2. Fallback to plain field
            return getattr(self, plain_field_name, None)

        # Helper for JSON blob fields
        def get_json_value(encrypted_field_name, plain_field_name):
            encrypted_val = getattr(self, encrypted_field_name, None)
            if isinstance(encrypted_val, str):
                try:
                    decrypted_json = EncryptionService.decrypt_data(encrypted_val)
                    return json.loads(decrypted_json)
                except Exception:
                    pass
            return getattr(self, plain_field_name, [])

        return {
           "CIN_1": get_value("CIN_1_encrypted", "CIN_1"),
           "CIN_2": get_value("CIN_2_encrypted", "CIN_2"),
           "basic_details": get_json_value("basic_details_encrypted", "basic_details"),
           "patient_details": get_json_value("patient_details_encrypted", "patient_details"),
           "diagnosis": get_json_value("diagnosis_encrypted", "diagnosis"),
           "clinical_details": get_json_value("clinical_details_encrypted", "clinical_details"),
           "prescribed_items": get_json_value("prescribed_items_encrypted", "prescribed_items"),
           "summary": get_value("summary_encrypted", "summary"),
           "CIN_1_search_hash": self.CIN_1_search_hash,
           "CIN_2_search_hash": self.CIN_2_search_hash,
        }

    def to_dict(self) -> dict:
        """Convert to dictionary for MongoDB storage"""
        return self.dict(exclude_none=True)




class Encrypted_OldPrescription(BaseModel):
    """
    [LEGACY] Represents an older encrypted prescription format.
    Kept for backward compatibility with existing records.
    Similar to Encrypted_Prescription but may lack some newer fields (e.g., CIN_2).
    """
    CIN_1_encrypted: str = Field(..., description="CIN (unique ID) of the patient")
    basic_details_encrypted: str = Field(..., description="Basic details of the consultation")
    patient_details_encrypted: str = Field(..., description="Details of the patient")
    diagnosis_encrypted: str = Field(..., description="Diagnosis details including symptoms and description")
    clinical_details_encrypted: str = Field(..., description="Clinical details of the clinic or hospital")
    prescribed_items_encrypted: str = Field(..., description="List of prescribed items")
    summary_encrypted: str = Field(..., description="Summary of the consultation")
    CIN_1_search_hash: str = Field(..., description="Hash of the CIN (unique ID) of the patient")

    class Config:
        extra = "allow"

    @classmethod
    def encrypt_user(cls, user_data: dict):
        """Create encrypted user from plain user data"""
        try:
            email = user_data.get("email", "")
            prescribed_items = user_data.get("prescribed_items", [])
            prescribed_items_json = json.dumps(prescribed_items)
            return cls(
                CIN_1_encrypted=EncryptionService.encrypt_data(user_data.get("CIN_1", "")),
                basic_details_encrypted=EncryptionService.encrypt_data(json.dumps(user_data.get("basic_details", {}))),
                patient_details_encrypted=EncryptionService.encrypt_data(json.dumps(user_data.get("patient_details", {}))),
                diagnosis_encrypted=EncryptionService.encrypt_data(json.dumps(user_data.get("diagnosis", {}))),
                clinical_details_encrypted=EncryptionService.encrypt_data(json.dumps(user_data.get("clinical_details", {}))),
                prescribed_items_encrypted=EncryptionService.encrypt_data(prescribed_items_json),
                summary_encrypted=EncryptionService.encrypt_data(json.dumps(user_data.get("summary", {}))),
                CIN_1_search_hash=EncryptionService.hash_data(user_data.get("CIN_1", "")),
            )
        except Exception as e:
            logger("CuraDocs_Doctor_CuraBot", "Encrypted_OldPrescription", "ERROR", "CRITICAL", f"Old Prescription Encryption failed: {str(e)}")
            raise

    def decrypt_user(self) -> dict:
        """Convert encrypted user to plain user data"""
        # Helper to safely decrypt and cast
        def get_value(encrypted_field_name, plain_field_name, cast_type=str):
            # 1. Try encrypted field
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
            
            # 2. Fallback to plain field
            return getattr(self, plain_field_name, None)

        # Helper for JSON blob fields
        def get_json_value(encrypted_field_name, plain_field_name):
            encrypted_val = getattr(self, encrypted_field_name, None)
            if isinstance(encrypted_val, str):
                try:
                    decrypted_json = EncryptionService.decrypt_data(encrypted_val)
                    return json.loads(decrypted_json)
                except Exception:
                    pass
            return getattr(self, plain_field_name, [])

        return {
           "CIN_1": get_value("CIN_1_encrypted", "CIN_1"),
           "basic_details": get_json_value("basic_details_encrypted", "basic_details"),
           "patient_details": get_json_value("patient_details_encrypted", "patient_details"),
           "diagnosis": get_json_value("diagnosis_encrypted", "diagnosis"),
           "clinical_details": get_json_value("clinical_details_encrypted", "clinical_details"),
           "prescribed_items": get_json_value("prescribed_items_encrypted", "prescribed_items"),
           "summary": get_value("summary_encrypted", "summary"),
           "CIN_1_search_hash": self.CIN_1_search_hash
        }

    def to_dict(self) -> dict:
        """Convert to dictionary for MongoDB storage"""
        return self.dict(exclude_none=True)

class EncryptedUser(BaseModel):
    """
    Represents an encrypted user (doctor/patient) for shared auth logic.
    Provides utility to decrypt fields into a plain dictionary.
    """
    first_name_encrypted: str = Field(default=None)
    last_name_encrypted: str = Field(default=None)
    email_encrypted: str = Field(default=None)
    
    # Allow extra fields safely
    class Config:
        extra = "allow"

    def to_plain_user(self) -> dict:
        """
        Decrypts specific encrypted fields and returns the full dictionary.
        This provides compatibility with the 'auth' service logic.
        """
        user_dict = self.dict(exclude_none=True)
        
        # Mapping of encrypted fields to plain fields
        fields_to_decrypt = {
            "first_name_encrypted": "first_name",
            "last_name_encrypted": "last_name",
            "email_encrypted": "email",
             # Add other fields if necessary
        }

        for enc_field, plain_field in fields_to_decrypt.items():
            if enc_field in user_dict:
                 try:
                     decrypted = EncryptionService.decrypt_data(user_dict[enc_field])
                     user_dict[plain_field] = decrypted
                     # Optionally remove the encrypted key from the result if desired, 
                     # otherwise keep both. Typically we just add the plain.
                 except Exception:
                     # If decryption fails, keep original or log? 
                     # For robustness we might just leave it.
                     pass
        
        return user_dict
