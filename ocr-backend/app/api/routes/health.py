"""Health check endpoint."""

from datetime import datetime

from fastapi import APIRouter

from app.models.document import HealthCheckResponse
from app.config import settings
from app import __version__

router = APIRouter(tags=["Health"])


@router.get("/health", response_model=HealthCheckResponse)
async def health_check():
    """
    Health check endpoint.
    
    Returns service status and availability of configured services.
    """
    services = {
        "gemini": bool(settings.gemini_api_key),
        "mongodb": settings.use_mongodb,
        "minio": settings.use_minio,
        "local_storage": not settings.use_minio
    }
    
    return HealthCheckResponse(
        status="healthy",
        timestamp=datetime.utcnow(),
        version=__version__,
        services=services
    )
