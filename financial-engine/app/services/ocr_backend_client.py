import httpx
import logging
import asyncio
from typing import Dict, Any

logger = logging.getLogger(__name__)

class OcrBackendClient:
    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url

    async def upload_document(self, filename: str, file: bytes) -> Dict[str, Any]:
        """Upload a document to the OCR backend"""
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                files = {"file": (filename, file)}
                response = await client.post(f"{self.base_url}/api/documents/upload", files=files)
                response.raise_for_status()
                return response.json()
        except httpx.HTTPError as e:
            logger.error(f"Error uploading document to OCR backend: {e}")
            raise Exception(f"OCR backend upload failed: {e}")

    async def get_document_content(self, document_id: str) -> bytes:
        """Get the raw document content (PDF bytes) from OCR backend"""
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(f"{self.base_url}/api/documents/{document_id}/content")
                response.raise_for_status()
                return response.content
        except httpx.HTTPError as e:
            logger.error(f"Error fetching document content from OCR backend: {e}")
            raise Exception(f"OCR backend fetch failed: {e}")

    async def get_document_text(self, document_id: str) -> str:
        """Get the extracted text from OCR backend"""
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(f"{self.base_url}/api/documents/{document_id}/text")
                response.raise_for_status()
                result = response.json()
                return result.get("text", "") if isinstance(result, dict) else result
        except httpx.HTTPError as e:
            logger.error(f"Error fetching document text from OCR backend: {e}")
            raise Exception(f"OCR backend text fetch failed: {e}")

    async def get_document_status(self, document_id: str) -> Dict[str, Any]:
        """Get the processing status of a document"""
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(f"{self.base_url}/api/documents/{document_id}/status")
                response.raise_for_status()
                return response.json()
        except httpx.HTTPError as e:
            logger.error(f"Error fetching document status from OCR backend: {e}")
            raise Exception(f"OCR backend status check failed: {e}")

    async def get_document_bytes(self, document_id: str) -> bytes:
        """Get the raw document bytes from OCR backend"""
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(f"{self.base_url}/api/documents/{document_id}/content")
                response.raise_for_status()
                return response.content
        except httpx.HTTPError as e:
            logger.error(f"Error fetching document bytes from OCR backend: {e}")
            raise Exception(f"OCR backend bytes fetch failed: {e}")