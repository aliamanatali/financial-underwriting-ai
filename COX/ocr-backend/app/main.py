"""FastAPI application entry point."""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import settings
from app.api.routes import health_router, documents_router
from app.utils.logger import logger
from app import __version__


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    # Startup
    logger.info("Starting OCR Backend API")
    logger.info(f"Version: {__version__}")
    logger.info(f"Gemini Model: {settings.gemini_model}")
    logger.info(f"Storage: {'MinIO' if settings.use_minio else 'Local'}")
    logger.info(f"Database: {'MongoDB' if settings.use_mongodb else 'In-Memory'}")
    
    yield
    
    # Shutdown
    logger.info("Shutting down OCR Backend API")


# Create FastAPI application
app = FastAPI(
    title="OCR Backend API",
    description="Document text extraction using Google Gemini API",
    version=__version__,
    lifespan=lifespan
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Global exception handler
@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    """Handle uncaught exceptions."""
    logger.error(f"Unhandled exception: {str(exc)}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={
            "detail": "Internal server error",
            "error": str(exc) if settings.debug else "An error occurred"
        }
    )


# Register routes
app.include_router(health_router)
app.include_router(documents_router)


@app.get("/")
async def root():
    """Root endpoint with API information."""
    return {
        "name": "OCR Backend API",
        "version": __version__,
        "description": "Document text extraction using Google Gemini API",
        "endpoints": {
            "health": "/health",
            "docs": "/docs",
            "upload": "POST /api/documents/upload",
            "get_document": "GET /api/documents/{document_id}",
            "get_text": "GET /api/documents/{document_id}/text",
            "delete": "DELETE /api/documents/{document_id}",
            "reprocess": "POST /api/documents/{document_id}/reprocess"
        }
    }


if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run(
        "app.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug,
        log_level=settings.log_level.lower()
    )
