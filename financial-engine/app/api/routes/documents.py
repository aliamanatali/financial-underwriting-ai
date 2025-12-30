from fastapi import APIRouter, Depends, UploadFile, File
from typing import List, Dict, Any
import httpx

router = APIRouter()

class OcrClient:
    def __init__(self, base_url: str):
        self.base_url = base_url

    async def upload_document(self, file: bytes) -> Dict[str, Any]:
        async with httpx.AsyncClient() as client:
            files = {"file": file}
            response = await client.post(f"{self.base_url}/api/documents/upload", files=files)
            response.raise_for_status()
            return response.json()

def get_ocr_client():
    return OcrClient(base_url="http://localhost:8001")

@router.get("/documents", response_model=List)
async def list_documents():
    return []

@router.post("/documents/upload")
async def upload_document(
    file: UploadFile = File(...),
    ocr_client: OcrClient = Depends(get_ocr_client),
):
    file_bytes = await file.read()
    return await ocr_client.upload_document(file_bytes)