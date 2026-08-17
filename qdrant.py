from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct
from curabot.config.database import db_settings
from curabot.logger.log import logger
class QdrantConfig:
    """
    Configuration and client management for Qdrant Vector Database.
    Handles connection initialization and collection management.
    """
    def __init__(self):
        # Initialize client using database settings
        self.client = db_settings.get_qdrant_client()
    
    async def create_collection(self, collection_name: str, vector_size: int = 384):
        """
        Create a new Qdrant collection if it doesn't already exist.
        
        Args:
            collection_name (str): Name of the collection to create.
            vector_size (int): Dimension of the vectors (default: 384 for all-MiniLM-L6-v2).
        """
        try:
            logger("CuraDocs_Doctor_CuraBot", "Qdrant", "INFO", "null", f"Checking validity of collection: '{collection_name}'")
            collections = self.client.get_collections()
            existing_names = [col.name for col in collections.collections]
            
            if collection_name not in existing_names:
                self.client.create_collection(
                    collection_name=collection_name,
                    vectors_config=VectorParams(size=vector_size, distance=Distance.COSINE)
                )
                logger("CuraDocs_Doctor_CuraBot", "Qdrant", "INFO", "null", f"Collection '{collection_name}' created successfully")
            else:
                logger("CuraDocs_Doctor_CuraBot", "Qdrant", "INFO", "null", f"Collection '{collection_name}' already exists, skipping creation.")
        except Exception as e:
            logger("CuraDocs_Doctor_CuraBot", "Qdrant", "ERROR", "CRITICAL", f"Error managing/creating collection '{collection_name}': {e}")
            
    async def check_health(self) -> bool:
        """Check Qdrant connection health"""
        try:
            self.client.get_collections()
            return True
        except Exception as e:
            logger("CuraDocs_Doctor_CuraBot", "Qdrant", "ERROR", "CRITICAL", f"Qdrant health check failed: {e}")
            return False


qdrant_config = QdrantConfig()