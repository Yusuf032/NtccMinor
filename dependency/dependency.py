from curabot.core.security import oauth2_scheme_doctor, oauth2_scheme_patient

from curabot.config.redis import is_jti_blacklisted
from fastapi import Depends, HTTPException, status
from typing import Annotated, Dict
from curabot.helper.utils import decode_access_token
from curabot.config.database import doctor_collection_name, patient_collection_name
from curabot.logger.log import logger
from curabot.security.encryption import EncryptionService
from curabot.model.encrypted_model import EncryptedUser 

async def _get_access_token(token: str) -> dict:
    """
    Decode and validate a JWT access token.

    Checks signature, expiration, and blacklisted status.

    Args:
        token (str): The JWT string.

    Returns:
        dict: The decoded token payload.

    Raises:
        HTTPException: 401 if invalid, expired, or blacklisted.
    """
    try:
        data = decode_access_token(token)
        if data is None:
            logger("CuraDocs_Doctor_CuraBot", "Token Validation", "WARN", "MEDIUM", "Invalid token format or expired")

            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired access token",
            )
        
        if await is_jti_blacklisted(data["jti"]):
            logger("CuraDocs_Doctor_CuraBot", "Token Validation", "WARN", "HIGH", f"Blacklisted token attempted: {data['jti'][:10]}...")

            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired access token",
            )
        
        logger("CuraDocs_Doctor_CuraBot", "Token Validation", "INFO", "null", "Token validation successful")

        return data
    except HTTPException:
        raise
    except Exception as e:
        logger("CuraDocs_Doctor_CuraBot", "Token Validation", "ERROR", "ERROR", f"Token validation error: {str(e)}")

        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token validation failed",
        )


async def get_doctor_access_token(token: Annotated[str, Depends(oauth2_scheme_doctor)]):
    """Dependency to retrieve and validate doctor access token."""
    return await _get_access_token(token)


async def get_patient_access_token(token: Annotated[str, Depends(oauth2_scheme_patient)]):
    """Dependency to retrieve and validate patient access token."""
    return await _get_access_token(token)


async def get_current_doctor(
    token_data: Annotated[dict, Depends(get_doctor_access_token)],
    token: str = Depends(oauth2_scheme_doctor)
) -> dict:
    """
    Retrieve current doctor profile from database using token data.

    Supports hybrid lookup (hash or plain CIN) and handles on-the-fly decryption.

    Args:
        token_data (dict): The payload from the validated JWT.

    Returns:
        dict: The decrypted doctor user object.

    Raises:
        HTTPException: 401 if token missing ID, 404 if user not found.
    """
    try:
        if "CIN" not in token_data:
            logger("CuraDocs_Doctor_CuraBot", "User Lookup", "WARN", "MEDIUM", "Token missing user ID")

            raise HTTPException(status_code=401, detail="Token payload missing 'id'")
        
        # Hybrid lookup: hash or plain
        query = {
            "$or": [
                {"CIN_hash": EncryptionService.hash_data(token_data["CIN"])},
                {"CIN": token_data["CIN"]}
            ]
        }
        user = await doctor_collection_name.find_one(query)
        
        if not user:
            logger("CuraDocs_Doctor_CuraBot", "User Lookup", "WARN", "MEDIUM", f"Doctor not found: {EncryptionService.hash_data(token_data['CIN'])}")

            raise HTTPException(status_code=404, detail="Doctor not found")
        
        # Check if user needs decryption
        if "first_name_encrypted" in user:
            user.pop("_id", None)
            user_model = EncryptedUser(**user)
            user = user_model.to_plain_user()

        logger("CuraDocs_Doctor_CuraBot", "User Lookup", "INFO", "null", f"Doctor retrieved successfully: {EncryptionService.hash_data(token_data['CIN'])}")

        
        user["CIN"] = token_data["CIN"] # Ensure CIN from token for subsequent logic
        user["access_token"] = token
        return user
    except HTTPException:
        raise
    except Exception as e:
        logger("CuraDocs_Doctor_CuraBot", "User Lookup", "ERROR", "ERROR", f"Doctor lookup error: {str(e)}")

        raise HTTPException(status_code=500, detail="User lookup failed")


async def get_current_patient(
    token_data: Annotated[dict, Depends(get_patient_access_token)],
    token: str = Depends(oauth2_scheme_patient)
) -> dict:
    """
    Retrieve current patient profile from database using token data.

    Supports hybrid lookup (hash or plain CIN) and handles on-the-fly decryption.

    Args:
        token_data (dict): The payload from the validated JWT.

    Returns:
        dict: The decrypted patient user object.

    Raises:
        HTTPException: 401 if token missing ID, 404 if user not found.
    """
    try:
        if "CIN" not in token_data:
            logger("CuraDocs_Doctor_CuraBot", "User Lookup", "WARN", "MEDIUM", "Token missing user ID")

            raise HTTPException(status_code=401, detail="Token payload missing 'id'")
        
        # Hybrid lookup: hash or plain
        query = {
            "$or": [
                {"CIN_hash": EncryptionService.hash_data(token_data["CIN"])},
                {"CIN": token_data["CIN"]}
            ]
        }
        user = await patient_collection_name.find_one(query)
        
        if not user:
            logger("CuraDocs_Doctor_CuraBot", "User Lookup", "WARN", "MEDIUM", f"Patient not found: {EncryptionService.hash_data(token_data['CIN'])}")

            raise HTTPException(status_code=404, detail="Patient not found")
        
        # Check if user needs decryption
        if "first_name_encrypted" in user:
            user.pop("_id", None)
            user_model = EncryptedUser(**user)
            user = user_model.to_plain_user()

        logger("CuraDocs_Doctor_CuraBot", "User Lookup", "INFO", "null", f"Patient retrieved successfully: {EncryptionService.hash_data(token_data['CIN'])}")

        
        user["CIN"] = token_data["CIN"] # Ensure CIN from token logic
        user["access_token"] = token
        return user
    except HTTPException:
        raise
    except Exception as e:
        logger("CuraDocs_Doctor_CuraBot", "User Lookup", "ERROR", "ERROR", f"Patient lookup error: {str(e)}")

        raise HTTPException(status_code=500, detail="Patient lookup failed")


DoctorDep = Annotated[Dict, Depends(get_current_doctor)]
PatientDep = Annotated[Dict, Depends(get_current_patient)]
