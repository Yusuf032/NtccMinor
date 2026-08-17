from pydantic_settings import SettingsConfigDict,BaseSettings
_base_config=SettingsConfigDict(
        env_file="./.env",  # ✅ make sure .env is in root or adjust path
        env_ignore_empty=True,
        extra="ignore"
    )
class SecuritySettings(BaseSettings):
    JWT_SECRET:str
    JWT_ALGORITHM:str

    model_config = _base_config
# Ensure that .env file contains JWT_SECRET and JWT_ALGORITHM variables
security_settings = SecuritySettings()