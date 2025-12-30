from fastapi import FastAPI
from app.api.routes import analysis, documents
from dotenv import load_dotenv
from fastapi.middleware.cors import CORSMiddleware

load_dotenv()

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
app.include_router(documents.router, prefix="/api", tags=["Documents"])

@app.get("/health", tags=["Health"])
async def health_check():
    return {"status": "ok"}
import logging

logging.basicConfig(level=logging.INFO)