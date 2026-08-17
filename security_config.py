from pydantic_settings import BaseSettings
from typing import List
import secrets

class SecuritySettings(BaseSettings):
    """Security configuration settings"""
    
    # Rate limiting
    RATE_LIMIT_REQUESTS: int = 100
    RATE_LIMIT_WINDOW: int = 3600  # 1 hour
    
    # Password policy
    MIN_PASSWORD_LENGTH: int = 8
    REQUIRE_UPPERCASE: bool = True
    REQUIRE_LOWERCASE: bool = True
    REQUIRE_DIGITS: bool = True
    REQUIRE_SPECIAL_CHARS: bool = True
    
    # JWT Security
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    JWT_REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    JWT_ALGORITHM: str = "HS256"
    
    # CORS Settings
    ALLOWED_ORIGINS: List[str] = ["http://localhost:3000", "https://www.curadocs.in","http://ui-service:3000","https://auth.curadocs.in","https://auth-dev.curadocs.in","https://dev.curadocs.in"]
    ALLOWED_METHODS: List[str] = ["GET", "POST", "PUT", "DELETE", "OPTIONS", "PATCH"]
    
    # Security Headers
    ENABLE_SECURITY_HEADERS: bool = True
    CONTENT_SECURITY_POLICY: str = "default-src 'self'"
    
    # Input Validation
    MAX_REQUEST_SIZE: int = 1024 * 1024  # 1MB
    MAX_STRING_LENGTH: int = 1000
    
    # Session Security
    SECURE_COOKIES: bool = True
    HTTPONLY_COOKIES: bool = True
    SAMESITE_COOKIES: str = "strict"
    
    class Config:
        env_file = ".env"
        env_ignore_empty = True
        extra = "ignore"

# Global security settings instance
security_settings = SecuritySettings()

def generate_secure_token(length: int = 32) -> str:
    """Generate cryptographically secure random token"""
    return secrets.token_urlsafe(length)

def generate_csrf_token() -> str:
    """Generate CSRF token"""
    return secrets.token_hex(16)