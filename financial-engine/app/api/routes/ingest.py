from fastapi import APIRouter, Depends, UploadFile, File, HTTPException
from app.services.ingestion_service import IngestionService
from app.models.schemas import UnderwritingAnalysis
from app.dependencies import get_ingestion_service
from app.services.ocr_backend_client import OcrBackendClient
from typing import List

router = APIRouter()

@router.get("/documents", response_model=List)
async def list_documents():
    """
    Returns a list of documents. This is a placeholder to ensure the frontend
    does not break while the ingestion endpoint is being used.
    """
    return []

@router.post("/analyze/ingest", response_model=UnderwritingAnalysis)
async def ingest_and_analyze_document(
    file: UploadFile = File(...),
    ingestion_service: IngestionService = Depends(get_ingestion_service),
):
    """
    Accepts a PDF file, sends it to the OCR backend, and performs a full
    underwriting analysis.
    """
    try:
        # 1. Upload the document to the ocr-backend to get a document_id
        ocr_client = OcrBackendClient()
        file_bytes = await file.read()
        upload_response = await ocr_client.upload_document(file.filename, file_bytes)
        document_id = upload_response["document_id"]

        # 2. Ingest and process the document using the document_id
        analysis = await ingestion_service.ingest_pdf_document(document_id)
        return analysis

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))