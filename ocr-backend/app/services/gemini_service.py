"""Gemini AI service for document text extraction."""

import base64
import re
import asyncio
import random
from typing import Optional

import google.generativeai as genai
from google.api_core import retry
from google.api_core.exceptions import DeadlineExceeded, ResourceExhausted, GoogleAPIError

from app.config import settings
from app.models.document import (
    DocumentExtractionResult,
    DocumentMetadata,
    ConfidenceLevel
)
from app.utils.logger import logger


# Global semaphore to limit concurrent Gemini API requests
# This prevents overwhelming the API with too many simultaneous requests
_gemini_semaphore = None

def get_gemini_semaphore():
    """Get or create the global Gemini API semaphore."""
    global _gemini_semaphore
    if _gemini_semaphore is None:
        # Limit to 4 concurrent requests to Gemini API (conservative for reliability)
        _gemini_semaphore = asyncio.Semaphore(4)
    return _gemini_semaphore


# DocuMind Extraction Prompt - Zero Hallucination Document Digitization
DOCUMIND_EXTRACTION_PROMPT = """You are DocuMind, a high-fidelity document digitization system. Your task is to extract ALL text from this PDF document with ZERO hallucination.

CORE PRINCIPLES:
1. NO HALLUCINATION: Never invent, infer, or add information not present in the document
2. NO SUMMARIZATION: Extract the full content, not summaries
3. PRESERVE FIDELITY: Maintain original spelling, punctuation, casing, and formatting

OUTPUT FORMAT:
For each page, use this structure:

--- PAGE [number] ---
[Extract all visible text exactly as it appears]

[Use these annotations for non-text elements:]
- [Handwritten: text] - for handwritten content
- [Stamp: "text"] - for stamps or seals
- [Watermark: "text"] - for watermarks
- [Image: description] - for images/logos
- [Table: convert to markdown] - for tables
- [Redaction box present] - for redacted content
- [Uncertain: possible text] - for unclear content
- [Illegible: X words] - for unreadable text

[Page Confidence: High/Medium/Low | Justification: reason]

After all pages, include:

=== DOCUMENT EXTRACTION SUMMARY ===
TOTAL PAGES: [number]
OVERALL DOCUMENT CONFIDENCE: High/Medium/Low
DOCUMENT QUALITY: High/Medium/Low
HANDWRITING DETECTED: Yes/No
EXTRACTION NOTES: [any important notes]

CRITICAL RULES:
- Extract EVERYTHING visible, even if it seems redundant
- Preserve exact formatting, line breaks, and spacing where meaningful
- Never skip headers, footers, page numbers, or watermarks
- If text is unclear, mark it as [Uncertain: ...] rather than guessing
- Maintain the original document's structure and flow
"""


class GeminiService:
    """Service for interacting with Google Gemini API."""
    
    def __init__(self):
        """Initialize Gemini service with API key."""
        genai.configure(api_key=settings.gemini_api_key)
        self.model = genai.GenerativeModel(settings.gemini_model)
        self.timeout = settings.gemini_timeout_seconds
        self.max_retries = settings.gemini_max_retries
        self.semaphore = get_gemini_semaphore()
        logger.info(
            f"Initialized Gemini service with model: {settings.gemini_model}, "
            f"timeout: {self.timeout}s, max_retries: {self.max_retries}, "
            f"max_concurrent_api_requests: 4"
        )
    
    async def extract_pdf_content(self, pdf_data: bytes) -> DocumentExtractionResult:
        """
        Extract text content from PDF using Gemini API.
        
        Args:
            pdf_data: PDF file content as bytes
            
        Returns:
            DocumentExtractionResult with extracted text and metadata
            
        Raises:
            Exception: If extraction fails
        """
        try:
            logger.info("Starting PDF text extraction with Gemini")
            
            # Convert PDF to base64
            pdf_base64 = base64.b64encode(pdf_data).decode('utf-8')
            
            # Create PDF part for Gemini
            pdf_part = {
                'mime_type': 'application/pdf',
                'data': pdf_base64
            }
            
            # Generate content with Gemini
            response = self.model.generate_content(
                [pdf_part, DOCUMIND_EXTRACTION_PROMPT],
                generation_config={
                    'temperature': settings.gemini_temperature,
                    'max_output_tokens': settings.gemini_max_output_tokens
                }
            )
            
            # Extract text from response
            extracted_text = response.text if response.text else ""
            
            # Parse metadata from extracted text
            metadata = self._parse_extraction_metadata(extracted_text, len(pdf_data))
            
            logger.info(
                f"Successfully extracted {metadata.page_count} pages "
                f"with {metadata.quality} confidence"
            )
            
            return DocumentExtractionResult(
                text=extracted_text,
                page_count=metadata.page_count,
                confidence=metadata.quality,
                metadata=metadata
            )
            
        except DeadlineExceeded as e:
            logger.error(f"Gemini API timeout (60s exceeded): {str(e)}")
            raise Exception(
                "PDF processing timeout. This document is too large to process at once. "
                "Please try again - the system will automatically split it into smaller chunks."
            )
        except Exception as e:
            logger.error(f"Failed to extract PDF content: {str(e)}")
            raise
    
    async def extract_pdf_chunk(
        self,
        pdf_chunk: bytes,
        chunk_info: str = "",
        start_page: int = 1,
        end_page: int = 1
    ) -> DocumentExtractionResult:
        """
        Extract text from a PDF chunk with timeout handling and retry logic.
        
        Args:
            pdf_chunk: PDF chunk content as bytes
            chunk_info: Information about the chunk (e.g., "chunk 1 of 10")
            start_page: Starting page number of this chunk
            end_page: Ending page number of this chunk
            
        Returns:
            DocumentExtractionResult with extracted text and metadata
            
        Raises:
            Exception: If extraction fails after retries
        """
        try:
            logger.info(f"Starting PDF chunk extraction: {chunk_info} (pages {start_page}-{end_page})")
            
            # Convert PDF chunk to base64
            pdf_base64 = base64.b64encode(pdf_chunk).decode('utf-8')
            
            # Create PDF part for Gemini
            pdf_part = {
                'mime_type': 'application/pdf',
                'data': pdf_base64
            }
            
            # Create chunk-specific prompt
            chunk_prompt = self._create_chunk_prompt(chunk_info, start_page, end_page)
            
            # Enhanced retry logic with exponential backoff and jitter
            last_exception = None
            max_attempts = 5  # Increased from 3 to 5 for better resilience
            
            for attempt in range(max_attempts):
                try:
                    logger.info(
                        f"Attempt {attempt + 1}/{max_attempts} for {chunk_info}"
                    )
                    
                    # Add small random delay to prevent thundering herd
                    if attempt > 0:
                        jitter = random.uniform(0, 0.5)
                        await asyncio.sleep(jitter)
                    
                    # Use semaphore to limit concurrent API requests (prevents 499 errors)
                    async with self.semaphore:
                        # Generate content with timeout
                        response = await asyncio.wait_for(
                            self._generate_content_async(pdf_part, chunk_prompt),
                            timeout=self.timeout
                        )
                    
                    # Extract text from response
                    extracted_text = response.text if response.text else ""
                    
                    # Parse metadata from extracted text
                    metadata = self._parse_extraction_metadata(extracted_text, len(pdf_chunk))
                    
                    logger.info(
                        f"Successfully extracted {chunk_info}: "
                        f"{metadata.page_count} pages with {metadata.quality} confidence"
                    )
                    
                    return DocumentExtractionResult(
                        text=extracted_text,
                        page_count=metadata.page_count,
                        confidence=metadata.quality,
                        metadata=metadata
                    )
                    
                except asyncio.TimeoutError:
                    last_exception = Exception(
                        f"Timeout after {self.timeout}s for {chunk_info}"
                    )
                    logger.warning(
                        f"Timeout on attempt {attempt + 1}/{max_attempts} for {chunk_info}"
                    )
                    
                    # Longer wait for timeout errors
                    if attempt < max_attempts - 1:
                        wait_time = min((2 ** attempt) * 3, 30)  # 3, 6, 12, 24, 30 seconds (capped)
                        jitter = random.uniform(0, 2)
                        total_wait = wait_time + jitter
                        logger.info(f"Waiting {total_wait:.1f}s before retry due to timeout")
                        await asyncio.sleep(total_wait)
                        continue
                    
                except ResourceExhausted as e:
                    last_exception = e
                    logger.warning(
                        f"Rate limit hit on attempt {attempt + 1}/{max_attempts} for {chunk_info}: {str(e)}"
                    )
                    
                    # Much longer wait for rate limit errors
                    if attempt < max_attempts - 1:
                        wait_time = min((2 ** attempt) * 10, 60)  # 10, 20, 40, 60, 60 seconds (capped)
                        jitter = random.uniform(0, 5)
                        total_wait = wait_time + jitter
                        logger.info(f"Waiting {total_wait:.1f}s before retry due to rate limit")
                        await asyncio.sleep(total_wait)
                        continue
                
                except GoogleAPIError as e:
                    # Handle various Google API errors (499, 504, etc.)
                    error_str = str(e)
                    last_exception = e
                    
                    # Check if it's a retryable error
                    is_retryable = any(code in error_str for code in ['499', '504', '503', '429'])
                    
                    if is_retryable:
                        logger.warning(
                            f"Retryable API error on attempt {attempt + 1}/{max_attempts} for {chunk_info}: {error_str}"
                        )
                        
                        if attempt < max_attempts - 1:
                            # Exponential backoff with jitter for API errors
                            wait_time = min((2 ** attempt) * 5, 45)  # 5, 10, 20, 40, 45 seconds (capped)
                            jitter = random.uniform(0, 3)
                            total_wait = wait_time + jitter
                            logger.info(f"Waiting {total_wait:.1f}s before retry due to API error")
                            await asyncio.sleep(total_wait)
                            continue
                    else:
                        # Non-retryable error, fail immediately
                        logger.error(f"Non-retryable API error for {chunk_info}: {error_str}")
                        raise
                    
                except Exception as e:
                    last_exception = e
                    error_str = str(e)
                    logger.warning(
                        f"Error on attempt {attempt + 1}/{max_attempts} for {chunk_info}: {error_str}"
                    )
                    
                    # Check if error message contains retryable indicators
                    is_retryable = any(keyword in error_str.lower() for keyword in [
                        'cancelled', 'deadline', 'timeout', 'rate', 'quota', '499', '504', '503', '429'
                    ])
                    
                    if is_retryable and attempt < max_attempts - 1:
                        wait_time = min((2 ** attempt) * 4, 40)  # 4, 8, 16, 32, 40 seconds (capped)
                        jitter = random.uniform(0, 2)
                        total_wait = wait_time + jitter
                        logger.info(f"Waiting {total_wait:.1f}s before retry")
                        await asyncio.sleep(total_wait)
                        continue
                    elif not is_retryable:
                        # Non-retryable error, fail immediately
                        logger.error(f"Non-retryable error for {chunk_info}: {error_str}")
                        raise
            
            # All retries failed
            logger.error(f"All {max_attempts} attempts failed for {chunk_info}")
            raise last_exception or Exception(f"Failed to extract {chunk_info}")
            
        except Exception as e:
            logger.error(f"Failed to extract PDF chunk {chunk_info}: {str(e)}")
            raise
    
    async def _generate_content_async(self, pdf_part: dict, prompt: str):
        """
        Generate content asynchronously (wrapper for sync Gemini API).
        
        Args:
            pdf_part: PDF part dictionary for Gemini
            prompt: Extraction prompt
            
        Returns:
            Gemini API response
        """
        # Run the synchronous Gemini API call in a thread pool
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None,
            lambda: self.model.generate_content(
                [pdf_part, prompt],
                generation_config={
                    'temperature': settings.gemini_temperature,
                    'max_output_tokens': settings.gemini_max_output_tokens
                }
            )
        )
    
    def _create_chunk_prompt(
        self,
        chunk_info: str,
        start_page: int,
        end_page: int
    ) -> str:
        """
        Create a chunk-specific extraction prompt.
        
        Args:
            chunk_info: Information about the chunk
            start_page: Starting page number
            end_page: Ending page number
            
        Returns:
            Customized extraction prompt
        """
        return f"""You are DocuMind, a high-fidelity document digitization system. Your task is to extract ALL text from this PDF chunk with ZERO hallucination.

THIS IS {chunk_info.upper()} (Pages {start_page}-{end_page})

CORE PRINCIPLES:
1. NO HALLUCINATION: Never invent, infer, or add information not present in the document
2. NO SUMMARIZATION: Extract the full content, not summaries
3. PRESERVE FIDELITY: Maintain original spelling, punctuation, casing, and formatting

OUTPUT FORMAT:
For each page, use this structure:

--- PAGE [number] ---
[Extract all visible text exactly as it appears]

[Use these annotations for non-text elements:]
- [Handwritten: text] - for handwritten content
- [Stamp: "text"] - for stamps or seals
- [Watermark: "text"] - for watermarks
- [Image: description] - for images/logos
- [Table: convert to markdown] - for tables
- [Redaction box present] - for redacted content
- [Uncertain: possible text] - for unclear content
- [Illegible: X words] - for unreadable text

[Page Confidence: High/Medium/Low | Justification: reason]

After all pages in this chunk, include:

=== CHUNK EXTRACTION SUMMARY ===
CHUNK: {chunk_info}
PAGES IN CHUNK: {start_page}-{end_page}
TOTAL PAGES EXTRACTED: [number]
CHUNK CONFIDENCE: High/Medium/Low
CHUNK QUALITY: High/Medium/Low
HANDWRITING DETECTED: Yes/No
EXTRACTION NOTES: [any important notes]

CRITICAL RULES:
- Extract EVERYTHING visible, even if it seems redundant
- Preserve exact formatting, line breaks, and spacing where meaningful
- Never skip headers, footers, page numbers, or watermarks
- If text is unclear, mark it as [Uncertain: ...] rather than guessing
- Maintain the original document's structure and flow
"""
    
    def _parse_extraction_metadata(
        self,
        extracted_text: str,
        file_size: int
    ) -> DocumentMetadata:
        """
        Parse metadata from extracted text.
        
        Args:
            extracted_text: The extracted text content
            file_size: Size of the original file in bytes
            
        Returns:
            DocumentMetadata object
        """
        # Count pages
        page_count = len(re.findall(r'--- PAGE \d+ ---', extracted_text))
        
        # Detect handwriting
        has_handwriting = bool(re.search(
            r'\[Handwritten:', 
            extracted_text, 
            re.IGNORECASE
        ))
        
        # Extract confidence from summary
        confidence = self._extract_confidence_level(extracted_text)
        
        # Extract notes
        notes_match = re.search(
            r'EXTRACTION NOTES:\s*(.+?)(?:\n|$)',
            extracted_text,
            re.IGNORECASE
        )
        extraction_notes = notes_match.group(1).strip() if notes_match else None
        
        return DocumentMetadata(
            page_count=page_count,
            has_handwriting=has_handwriting,
            quality=confidence,
            file_size=file_size,
            mime_type="application/pdf",
            extraction_notes=extraction_notes
        )
    
    def _extract_confidence_level(self, text: str) -> ConfidenceLevel:
        """
        Extract confidence level from extraction summary.
        
        Args:
            text: Extracted text containing summary
            
        Returns:
            ConfidenceLevel enum value
        """
        # Look for overall confidence in summary
        confidence_match = re.search(
            r'OVERALL DOCUMENT CONFIDENCE:\s*(High|Medium|Low)',
            text,
            re.IGNORECASE
        )
        
        if confidence_match:
            confidence_str = confidence_match.group(1).lower()
            if confidence_str == 'high':
                return ConfidenceLevel.HIGH
            elif confidence_str == 'medium':
                return ConfidenceLevel.MEDIUM
            else:
                return ConfidenceLevel.LOW
        
        # Fallback: check for uncertain/illegible markers
        uncertain_count = len(re.findall(r'\[Uncertain:', text))
        illegible_count = len(re.findall(r'\[Illegible:', text))
        
        if uncertain_count + illegible_count > 10:
            return ConfidenceLevel.LOW
        elif uncertain_count + illegible_count > 3:
            return ConfidenceLevel.MEDIUM
        else:
            return ConfidenceLevel.HIGH
    
    async def generate_embeddings(
        self,
        text: str,
        dimensions: int = 768
    ) -> list[float]:
        """
        Generate embeddings for text using Gemini embedding model.
        
        Args:
            text: Text to generate embeddings for
            dimensions: Embedding dimensions (128, 256, 512, 768, or 3072)
            
        Returns:
            List of embedding values
        """
        try:
            result = genai.embed_content(
                model=settings.gemini_embedding_model,
                content=text,
                task_type="retrieval_document"
            )
            
            embedding = result['embedding']
            
            # Matryoshka truncation if needed
            if dimensions < len(embedding):
                embedding = embedding[:dimensions]
            
            return embedding
            
        except Exception as e:
            logger.error(f"Failed to generate embeddings: {str(e)}")
            raise
