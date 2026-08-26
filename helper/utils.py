import random    
import string
import secrets
from itsdangerous import BadSignature,Serializer,URLSafeSerializer,URLSafeTimedSerializer,SignatureExpired
from fastapi import HTTPException, status
import jwt
from uuid import uuid4
from curabot.config.secert import security_settings
from phonenumbers.phonenumberutil import region_code_for_country_code
import pycountry
from passlib.context import CryptContext
from curabot.logger.log import logger
from pathlib import Path
from datetime import datetime,timezone,timedelta

APP_DIR= Path(__file__).resolve().parent
TEMPLATE_DIR = APP_DIR.parent / "templates"
_serializer=URLSafeTimedSerializer(security_settings.JWT_SECRET)
# Password hashing context
password_context=CryptContext(
    schemes=["argon2"],
    deprecated="auto"
)
"""Get country name from dial code for phone number validation"""
def get_country_from_dial_code(dial_code: str) -> str:
    try:
        # Remove '+' if present and convert to integer
        code = int(dial_code.strip().replace("+", ""))
        
        # Get ISO Alpha-2 region code (e.g., 'IN' for +91)
        region_code = region_code_for_country_code(code)
        if not region_code:
            logger("CuraDocs_Doctor_CuraBot", "Utils", "WARN", "LOW", f"Unrecognized dial code: {dial_code}")
            return "Country not recognized for this code."

        # Use pycountry to get full country name
        country = pycountry.countries.get(alpha_2=region_code)
        if country:
            logger("CuraDocs_Doctor_CuraBot", "Utils", "INFO", "null", f"Country resolved: {country.name} for dial code {dial_code}")
            return country.name
        else:
            logger("CuraDocs_Doctor_CuraBot", "Utils", "WARN", "LOW", f"Country not found for region code: {region_code}")
            return "Country not found in database."
    except Exception as e:
        logger("CuraDocs_Doctor_CuraBot", "Utils", "ERROR", "ERROR", f"Error resolving country for dial code {dial_code}: {str(e)}")
        return f"Invalid input: {e}"

"""Generate random alphanumeric ID for user identification"""
def id_generator(length=7):
    try:
        characters = string.ascii_letters + string.digits  # a-zA-Z0-9
        generated_id = ''.join(secrets.choice(characters) for _ in range(length))
        logger("CuraDocs_Doctor_CuraBot", "Utils", "INFO", "null", f"Generated ID with length: {length}")
        return generated_id
    except Exception as e:
        logger("CuraDocs_Doctor_CuraBot", "Utils", "ERROR", "ERROR", f"ID generation failed: {str(e)}")
        raise


"""Hash password using bcrypt for secure storage"""
def password_hash(password: str) -> str:
    try:
        hashed_password = password_context.hash(password)
        logger("CuraDocs_Doctor_CuraBot", "Utils", "INFO", "null", "Password hashed successfully")
        return hashed_password
    except Exception as e:
        logger("CuraDocs_Doctor_CuraBot", "Utils", "ERROR", "ERROR", f"Password hashing failed: {str(e)}")
        raise



"""Generate JWT access token with expiration and unique JTI"""
def generate_access_token(data:dict, expiry:timedelta=timedelta(days=1))->str:
    try:
        jti = str(uuid4())
        token = jwt.encode(
            payload={
                **data,
                "jti": jti,
                "exp": int((datetime.now(timezone.utc) + expiry).timestamp()),
            },
            algorithm=security_settings.JWT_ALGORITHM,
            key=security_settings.JWT_SECRET
        )
        logger("CuraDocs_Doctor_CuraBot", "Utils", "INFO", "null", f"Access token generated with JTI: {jti[:10]}...")
        return token
    except Exception as e:
        logger("CuraDocs_Doctor_CuraBot", "Utils", "ERROR", "ERROR", f"Access token generation failed: {str(e)}")
        raise


"""Decode and validate JWT access token"""
def decode_access_token(token:str)->dict| None:
    try:
        decoded_data = jwt.decode(
            jwt=token,
            key=security_settings.JWT_SECRET,
            algorithms=[security_settings.JWT_ALGORITHM]
        )
        logger("CuraDocs_Doctor_CuraBot", "Utils", "INFO", "null", "Access token decoded successfully")
        return decoded_data
    except jwt.ExpiredSignatureError:
        logger("CuraDocs_Doctor_CuraBot", "Utils", "WARN", "MEDIUM", "Access token expired")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Access Token has expired"
        )
    except jwt.PyJWTError as e:
        logger("CuraDocs_Doctor_CuraBot", "Utils", "WARN", "MEDIUM", f"Invalid access token: {str(e)}")
        return None
    except Exception as e:
        logger("CuraDocs_Doctor_CuraBot", "Utils", "ERROR", "ERROR", f"Access token decode error: {str(e)}")
        return None

"""Generate URL-safe token for email verification and password reset"""
def generate_url_safe_token(data:dict,salt:str|None=None)->str:
    try:
        token = _serializer.dumps(data,salt=salt)
        logger("CuraDocs_Doctor_CuraBot", "Utils", "INFO", "null", f"URL-safe token generated with salt: {salt or 'none'}")
        return token
    except Exception as e:
        logger("CuraDocs_Doctor_CuraBot", "Utils", "ERROR", "ERROR", f"URL-safe token generation failed: {str(e)}")
        raise


"""Decode URL-safe token for email verification and password reset"""
def decode_url_safe_token(token,salt:str,expiry:timedelta|None=None)->dict|None:
    try:
        decoded_data = _serializer.loads(token,salt=salt,max_age=expiry.total_seconds() if expiry else None)
        logger("CuraDocs_Doctor_CuraBot", "Utils", "INFO", "null", f"URL-safe token decoded successfully with salt: {salt}")
        return decoded_data
    except SignatureExpired:
        logger("CuraDocs_Doctor_CuraBot", "Utils", "WARN", "MEDIUM", "URL-safe token expired")
        return None
    except BadSignature:
        logger("CuraDocs_Doctor_CuraBot", "Utils", "WARN", "MEDIUM", "Invalid URL-safe token signature")
        return None
    except Exception as e:
        logger("CuraDocs_Doctor_CuraBot", "Utils", "ERROR", "ERROR", f"URL-safe token decode error: {str(e)}")
        return None


"""Generate JWT token for OTP verification"""
def generate_otp_token(data:dict, expiry:timedelta=timedelta(days=1))->str:
    try:
        token = jwt.encode(
            payload={
                **data,
                "exp": int((datetime.now(timezone.utc) + expiry).timestamp()),
            },
            algorithm=security_settings.JWT_ALGORITHM,
            key=security_settings.JWT_SECRET
        )
        logger("CuraDocs_Doctor_CuraBot", "Utils", "INFO", "null", "OTP token generated successfully")
        return token
    except Exception as e:
        logger("CuraDocs_Doctor_CuraBot", "Utils", "ERROR", "ERROR", f"OTP token generation failed: {str(e)}")
        raise


"""Decode and validate OTP JWT token"""
def decode_otp_token(token:str)->dict| None:
    try:
        decoded_data = jwt.decode(
            jwt=token,
            key=security_settings.JWT_SECRET,
            algorithms=[security_settings.JWT_ALGORITHM]
        )
        logger("CuraDocs_Doctor_CuraBot", "Utils", "INFO", "null", "OTP token decoded successfully")
        return decoded_data
    except jwt.ExpiredSignatureError:
        logger("CuraDocs_Doctor_CuraBot", "Utils", "WARN", "MEDIUM", "OTP token expired")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="OTP Token has expired"
        )
    except jwt.PyJWTError as e:
        logger("CuraDocs_Doctor_CuraBot", "Utils", "WARN", "MEDIUM", f"Invalid OTP token: {str(e)}")
        return None
    except Exception as e:
        logger("CuraDocs_Doctor_CuraBot", "Utils", "ERROR", "ERROR", f"OTP token decode error: {str(e)}")
        return None

# Helper: serialize ObjectId in Mongo docs
def serialize_mongo_doc(doc):
    doc = dict(doc)
    for k, v in doc.items():
        if isinstance(v, ObjectId):
            doc[k] = str(v)
        elif isinstance(v, list):
            doc[k] = [serialize_mongo_doc(x) if isinstance(x, dict) else x for x in v]
        elif isinstance(v, dict):
            doc[k] = serialize_mongo_doc(v)
    return doc
