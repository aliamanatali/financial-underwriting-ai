import httpx
from typing import Dict, Any

class OcrClient:
    def __init__(self, base_url: str):
        self.base_url = base_url

    async def upload_document(self, file: bytes) -> Dict[str, Any]:
        async with httpx.AsyncClient() as client:
            files = {"file": file}
            response = await client.post(f"{self.base_url}/api/documents/upload", files=files)
            response.raise_for_status()
            return response.json()

    async def get_document_text(self, document_id: str) -> Dict[str, Any]:
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{self.base_url}/api/documents/{document_id}/text")
            response.raise_for_status()
            return response.json()