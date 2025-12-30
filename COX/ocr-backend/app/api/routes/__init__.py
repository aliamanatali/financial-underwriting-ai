"""API route modules."""

from .health import router as health_router
from .documents import router as documents_router

__all__ = ["health_router", "documents_router"]
