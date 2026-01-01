from fastapi import FastAPI
import app.config  # Ensures config is loaded first
from app.api.routes import analysis, ingest, exports
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(
    title="Valiance Financial Engine",
    description="A service for performing financial analysis on real estate deals.",
    version="1.0.0"
)

origins = [
    "http://localhost:3000",
]

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