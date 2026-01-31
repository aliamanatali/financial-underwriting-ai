from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from app.config import settings
import logging

logger = logging.getLogger(__name__)

class MongoDB:
    client: AsyncIOMotorClient = None
    db: AsyncIOMotorDatabase = None

db = MongoDB()

async def connect_to_mongo():
    """Connect to MongoDB."""
    if not settings.use_mongodb:
        logger.warning("MongoDB not configured. Skipping connection.")
        return

    try:
        db.client = AsyncIOMotorClient(settings.mongodb_uri)
        db.db = db.client[settings.mongodb_database]
        # Verify connection
        await db.client.admin.command('ping')
        logger.info("Connected to MongoDB")
    except Exception as e:
        logger.error(f"Could not connect to MongoDB: {e}")
        raise

async def close_mongo_connection():
    """Close MongoDB connection."""
    if db.client:
        db.client.close()
        logger.info("MongoDB connection closed")

def get_database() -> AsyncIOMotorDatabase:
    """Return database instance."""
    return db.db