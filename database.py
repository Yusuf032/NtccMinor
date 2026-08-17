from motor.motor_asyncio import AsyncIOMotorClient
from pymongo import MongoClient
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import field_validator
from curabot.logger.log import logger 
from qdrant_client import QdrantClient
import asyncio
import html

_base_config=SettingsConfigDict(
        env_file="./.env",  #  make sure .env is in root or adjust path
        env_ignore_empty=True,
        extra="ignore"
    )

class DatabaseSettings(BaseSettings):
    REDIS_HOST: str
    REDIS_PORT: str
    MONGO_URL:str
    QDRANT_HOST: str 
    QDRANT_PORT: str 
    @field_validator("REDIS_PORT", mode="before")
    def parse_redis_port(cls, v: str) -> str:
        # Handle Kubernetes tcp:// service variable injection
        if v.startswith("tcp://"):
            try:
                # Format is tcp://IP:PORT for K8s service variables
                return v.rsplit(":", 1)[1]
            except IndexError:
                return v
        return v
    @field_validator("QDRANT_PORT", mode="before")
    def parse_qdrant_port(cls, v: str) -> str:
        # Handle Kubernetes tcp:// service variable injection
        if v.startswith("tcp://"):
            try:
                # Format is tcp://IP:PORT for K8s service variables
                return v.rsplit(":", 1)[1]
            except IndexError:
                return v
        return v

    def get_qdrant_client(self):
        return QdrantClient(host=str(self.QDRANT_HOST), port=int(self.QDRANT_PORT))

    def REDIS_URL(self, db) -> str:
        # Sanitize inputs to prevent XSS
        safe_host = html.escape(str(self.REDIS_HOST))
        safe_port = html.escape(str(self.REDIS_PORT))
        safe_db = html.escape(str(db))
        return f"redis://{safe_host}:{safe_port}/{safe_db}"
    def get_mongo_url(self):
        # Sanitize inputs to prevent XSS
        safe_url = html.escape(str(self.MONGO_URL))
        return safe_url
    model_config = _base_config
"""Check MongoDB connection health status"""
async def check_database_health():
    try:
        await client.admin.command('ping')
        logger("CuraDocs_Doctor_CuraBot", "Database", "INFO", "null", "Database connection successful")
        return True
    except Exception as e:
        # Sanitize error message to prevent XSS
        sanitized_error = html.escape(str(e))
        logger("CuraDocs_Doctor_CuraBot", "Database", "ERROR", "CRITICAL", f"Database connection failed: {sanitized_error}")
        return False

"""Continuously monitor database health every 60 seconds"""
async def monitor_database():
    while True:
        await check_database_health()
        await asyncio.sleep(300)  # Check every 60 seconds

async def create_db_indexes():
    """Create indexes for database collections"""
    try:
        await medical_records_collection.create_index("CIN_1_search_hash", unique=False, sparse=True)
        
        # Index for Doctor Search (hashed sensitive data)
        # unique=False because a doctor can create multiple records
        await medical_records_collection.create_index("CIN_2_search_hash", unique=False, sparse=True)
        
        # Banking indexes
        await banking_transactions_collection.create_index("customer_id_search_hash", unique=False, sparse=True)
        await banking_transactions_collection.create_index("account_id_search_hash", unique=False, sparse=True)
        await banking_transactions_collection.create_index("txn_id_search_hash", unique=False, sparse=True)
        
        logger("CuraDocs_Doctor_CuraBot", "Database", "INFO", "null", "Database indexes created successfully (medical + banking)")
    except Exception as e:
        logger("CuraDocs_Doctor_CuraBot", "Database", "ERROR", "CRITICAL", f"Failed to create indexes: {str(e)}")


# MongoDB connection setup
client = AsyncIOMotorClient(DatabaseSettings().get_mongo_url())
db_connection = client.medical_records
medical_records_collection = db_connection["medical_records"]

# Banking database collections
banking_db_connection = client.banking_records
banking_transactions_collection = banking_db_connection["banking_transactions"]

auth_db_connection = client.auth
doctor_collection_name = auth_db_connection["doctor"]
patient_collection_name = auth_db_connection["patient"]

# Memory collections
long_memory_collection_name = "long_memory"
db_name = "curabot"

def get_medical_records_collection():
    """Return the global async collection instance (compatibility wrapper)"""
    return medical_records_collection

def get_sync_medical_records_collection():
    """Return a synchronous PyMongo collection for use in Celery tasks"""
    settings = DatabaseSettings()
    client = MongoClient(settings.get_mongo_url())
    db = client.medical_records
    return db["medical_records"]

def get_banking_collection():
    """Return the global async banking collection instance"""
    return banking_transactions_collection

def get_sync_banking_collection():
    """Return a synchronous PyMongo banking collection for use in Celery tasks"""
    settings = DatabaseSettings()
    client = MongoClient(settings.get_mongo_url())
    db = client.banking_records
    return db["banking_transactions"]


db_settings = DatabaseSettings()
