from fastapi import FastAPI
import app.config  # Ensures config is loaded first
from app.api.routes import analysis, ingest, exports
from fastapi.middleware.cors import CORSMiddleware
import os
import json

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

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


app.include_router(analysis.router, prefix="/api/v1", tags=["Analysis"])
app.include_router(ingest.router, prefix="/api", tags=["Ingestion"])
app.include_router(exports.router, prefix="/api/v1", tags=["Exports"])

@app.get("/health", tags=["Health"])
async def health_check():
    return {"status": "ok"}
import logging

logging.basicConfig(level=logging.INFO)