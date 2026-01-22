from fastapi import FastAPI
import logging
import app.config  # Ensures config is loaded first
from app.api.routes import analysis, ingest, exports, multi_document, progress
from fastapi.middleware.cors import CORSMiddleware
import os
import json

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Valiance Financial Engine",
    description="A service for performing financial analysis on real estate deals.",
    version="1.0.0"
)

# Read CORS origins from environment variable
cors_origins_str = os.getenv("CORS_ORIGINS", '["http://localhost:3000"]')
try:
    origins = json.loads(cors_origins_str)
except json.JSONDecodeError:
    # Fallback to default if JSON parsing fails
    origins = ["http://localhost:3000"]

# Always include production URLs if not already present
production_urls = [
    "https://financial-underwriting-ai.onrender.com",
    "https://financial-underwriting-financial-engine.onrender.com"
]
for url in production_urls:
    if url not in origins:
        origins.append(url)

logger.info(f"CORS enabled for origins: {origins}")

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
)

# Increase the file upload limit
# Note: FastAPI/Starlette doesn't have a direct file size limit middleware by default,
# but server implementations (like uvicorn/gunicorn) or reverse proxies (nginx) usually handle this.
# However, we can add a middleware to handle potential large request bodies if needed,
# though standard FastAPI streaming handles large files efficiently.
# If running behind Nginx/Apache, their config needs adjustment (client_max_body_size).
# For dev/direct uvicorn, it streams, so typically no hard limit unless specified.


app.include_router(analysis.router, prefix="/api/v1", tags=["Analysis"])
app.include_router(ingest.router, prefix="/api", tags=["Ingestion"])
app.include_router(exports.router, prefix="/api/v1", tags=["Exports"])
app.include_router(multi_document.router, tags=["Multi-Document"])
app.include_router(progress.router, prefix="/api/v1", tags=["Progress"])

@app.get("/health", tags=["Health"])
async def health_check():
    return {"status": "ok"}
