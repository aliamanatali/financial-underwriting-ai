import logging
import json
import io
import asyncio
from typing import Optional, List, Dict, Tuple
from PyPDF2 import PdfReader
from app.models.schemas import DocumentType
from app.services.gemini_client import GeminiClient

logger = logging.getLogger(__name__)

class ClassificationService:
    """
    Service for classifying documents into standard DocumentTypes using Gemini.
    Uses content-based classification by analyzing first 3 and last 3 pages.
    """
    
    def __init__(self, gemini_service: GeminiClient):
        self.gemini_service = gemini_service

    def _extract_pdf_pages(self, pdf_content: bytes, max_pages_start: int = 3, max_pages_end: int = 3) -> Tuple[str, int]:
        """
        Extract text from first N and last N pages of a PDF.
        
        Args:
            pdf_content: PDF file content as bytes
            max_pages_start: Number of pages to extract from the beginning
            max_pages_end: Number of pages to extract from the end
            
        Returns:
            Tuple of (extracted_text, total_page_count)
        """
        try:
            pdf_file = io.BytesIO(pdf_content)
            reader = PdfReader(pdf_file)
            total_pages = len(reader.pages)
            
            extracted_text = []
            
            # Extract first N pages
            start_pages = min(max_pages_start, total_pages)
            for i in range(start_pages):
                try:
                    page_text = reader.pages[i].extract_text()
                    if page_text:
                        extracted_text.append(f"--- Page {i+1} ---\n{page_text}")
                except Exception as e:
                    logger.warning(f"Could not extract text from page {i+1}: {str(e)}")
            
            # Extract last N pages (if document has more than start_pages)
            if total_pages > max_pages_start:
                end_pages = min(max_pages_end, total_pages - max_pages_start)
                start_idx = total_pages - end_pages
                
                for i in range(start_idx, total_pages):
                    try:
                        page_text = reader.pages[i].extract_text()
                        if page_text:
                            extracted_text.append(f"--- Page {i+1} ---\n{page_text}")
                    except Exception as e:
                        logger.warning(f"Could not extract text from page {i+1}: {str(e)}")
            
            combined_text = "\n\n".join(extracted_text)
            return combined_text, total_pages
            
        except Exception as e:
            logger.error(f"Error extracting PDF pages: {str(e)}")
            return "", 0

    async def classify_file(self, filename: str, content: Optional[bytes] = None, content_preview: str = "") -> Optional[DocumentType]:
        """
        Classify a single file based on its content (first 3 and last 3 pages).
        Falls back to filename if content is not available.
        
        Args:
            filename: Original filename
            content: PDF file content as bytes (preferred)
            content_preview: Text preview (fallback if content not available)
            
        Returns:
            DocumentType or None if classification fails
        """
        try:
            # Extract content from PDF if provided
            extracted_content = ""
            total_pages = 0
            
            if content:
                # Check if it's a PDF
                if filename.lower().endswith('.pdf'):
                    extracted_content, total_pages = self._extract_pdf_pages(content)
                    logger.info(f"Extracted content from {total_pages} pages of {filename}")
                else:
                    # For non-PDF files, use content_preview or try to decode
                    try:
                        extracted_content = content.decode('utf-8', errors='ignore')[:2000]
                    except:
                        extracted_content = content_preview
            else:
                extracted_content = content_preview
            
            # If we have no content, fall back to filename-based classification
            if not extracted_content or len(extracted_content.strip()) < 50:
                logger.warning(f"Insufficient content for {filename}, using filename-based classification")
                return await self._classify_by_filename(filename)
            
            # Use LLM to classify based on content
            prompt = f"""
            You are a document classifier for commercial real estate underwriting.
            Analyze the following document content and classify it into exactly ONE of these categories:
            
            Categories:
            - {DocumentType.OFFERING_MEMORANDUM.value}: Marketing materials, property overview, executive summary, appraisal
            - {DocumentType.RENT_ROLL.value}: List of tenants, lease details, unit information, occupancy data
            - {DocumentType.LEASES.value}: Individual lease agreements, tenancy agreements
            - {DocumentType.FINANCIALS.value}: T12, P&L, Income Statements, Balance Sheets, Operating Statements, Historical financials
            - {DocumentType.BUILDING_PLANS_PERMITS.value}: Floor plans, site plans, permits, surveys, zoning documents
            - {DocumentType.DISCLOSURES.value}: Environmental reports, Phase I/II, PCA, inspection reports
            - {DocumentType.TAX_BILLS.value}: Property tax bills, tax returns, assessor documents
            - {DocumentType.UTILITIES.value}: Utility bills (water, electric, gas, sewer, trash)
            
            Document Filename: "{filename}"
            Total Pages: {total_pages if total_pages > 0 else 'Unknown'}
            
            Content (First 3 and Last 3 pages):
            {extracted_content[:4000]}
            
            Based on the CONTENT above (not just the filename), return ONLY the exact category name.
            If you cannot determine the category with confidence, return "Unknown".
            
            Category:"""
            
            response = await self.gemini_service.generate_content_async(prompt, use_fast_model=True)
            result = response.strip().replace('"', '').replace("'", "")
            
            # Match result to enum
            for doc_type in DocumentType:
                if doc_type.value.lower() == result.lower():
                    logger.info(f"Classified '{filename}' as {doc_type.value} based on content")
                    return doc_type
            
            # Try partial matches if exact match fails
            if "financial" in result.lower():
                return DocumentType.FINANCIALS
            if "rent" in result.lower() and "roll" in result.lower():
                return DocumentType.RENT_ROLL
            if "offering" in result.lower() or "memorandum" in result.lower():
                return DocumentType.OFFERING_MEMORANDUM
            if "lease" in result.lower():
                return DocumentType.LEASES
            if "tax" in result.lower():
                return DocumentType.TAX_BILLS
            if "utility" in result.lower() or "utilities" in result.lower():
                return DocumentType.UTILITIES
            if "plan" in result.lower() or "permit" in result.lower():
                return DocumentType.BUILDING_PLANS_PERMITS
            if "disclosure" in result.lower() or "environmental" in result.lower():
                return DocumentType.DISCLOSURES
            
            logger.info(f"LLM could not confidently classify '{filename}' (Result: {result}). Defaults to Unknown.")
            return None

        except Exception as e:
            logger.error(f"Error classifying file {filename}: {str(e)}")
            return None

    async def _classify_by_filename(self, filename: str) -> Optional[DocumentType]:
        """
        Fallback classification based on filename keywords.
        """
        filename_lower = filename.lower()
        
        if "rent roll" in filename_lower or "rentroll" in filename_lower:
            return DocumentType.RENT_ROLL
        if "t12" in filename_lower or "trailing 12" in filename_lower or "p&l" in filename_lower or "profit & loss" in filename_lower or "income statement" in filename_lower:
            return DocumentType.FINANCIALS
        if "om" in filename_lower or "offering memorandum" in filename_lower or "flyer" in filename_lower:
            return DocumentType.OFFERING_MEMORANDUM
        if "lease" in filename_lower and "agreement" in filename_lower:
            return DocumentType.LEASES
        if "tax" in filename_lower and "bill" in filename_lower:
            return DocumentType.TAX_BILLS
        if "utility" in filename_lower or "utilities" in filename_lower:
            return DocumentType.UTILITIES
        if "plan" in filename_lower or "permit" in filename_lower:
            return DocumentType.BUILDING_PLANS_PERMITS
        if "disclosure" in filename_lower or "environmental" in filename_lower:
            return DocumentType.DISCLOSURES
        
        return None

    async def classify_files_batch(
        self,
        files: List[Tuple[str, Optional[bytes]]] = None,
        filenames: List[str] = None
    ) -> Dict[str, DocumentType]:
        """
        Classify a batch of files using content-based analysis.
        
        Args:
            files: List of tuples (filename, content_bytes) - preferred method
            filenames: List of filenames only - fallback to filename-based classification
            
        Returns:
            Dictionary mapping filename to DocumentType
        """
        if not files and not filenames:
            return {}
        
        # If only filenames provided (legacy support), use filename-based classification
        if filenames and not files:
            return await self._classify_files_by_name_batch(filenames)
        
        # Content-based batch classification
        try:
            results = {}
            
            # Process files in parallel
            tasks = []
            for filename, content in files:
                tasks.append(self.classify_file(filename, content=content))
            
            classification_results = await asyncio.gather(*tasks)
            
            for i, doc_type in enumerate(classification_results):
                if doc_type:
                    filename = files[i][0]
                    results[filename] = doc_type
            
            return results
            
        except Exception as e:
            logger.error(f"Error in batch classification: {str(e)}")
            return {}

    async def _classify_files_by_name_batch(self, filenames: List[str]) -> Dict[str, DocumentType]:
        """
        Legacy method: Classify a batch of filenames using filename-based heuristics.
        """
        if not filenames:
            return {}
            
        try:
            prompt = f"""
            You are a document classifier for a commercial real estate underwriting system.
            Classify each of the following filenames into exactly one of these categories:
            
            Categories:
            - {DocumentType.OFFERING_MEMORANDUM.value}
            - {DocumentType.RENT_ROLL.value}
            - {DocumentType.LEASES.value}
            - {DocumentType.FINANCIALS.value}
            - {DocumentType.BUILDING_PLANS_PERMITS.value}
            - {DocumentType.DISCLOSURES.value}
            - {DocumentType.TAX_BILLS.value}
            - {DocumentType.UTILITIES.value}
            - Unknown
            
            Filenames to classify:
            {json.dumps(filenames, indent=2)}
            
            Return a JSON object where keys are the filenames and values are the category names.
            Example:
            {{
                "prop_t12.xlsx": "{DocumentType.FINANCIALS.value}",
                "unknown_file.txt": "Unknown"
            }}
            """
            
            response = await self.gemini_service.generate_content_async(prompt)
            
            # Clean response
            cleaned_text = response.strip()
            if cleaned_text.startswith("```json"):
                cleaned_text = cleaned_text[7:]
            if cleaned_text.startswith("```"):
                cleaned_text = cleaned_text[3:]
            if cleaned_text.endswith("```"):
                cleaned_text = cleaned_text[:-3]
            
            results_dict = json.loads(cleaned_text.strip())
            
            # Map strings to Enums
            final_map = {}
            for fname, cat_str in results_dict.items():
                matched = False
                for doc_type in DocumentType:
                    if doc_type.value.lower() == cat_str.lower():
                        final_map[fname] = doc_type
                        matched = True
                        break
                
                # Fallback heuristics for common mismatches
                if not matched:
                    if "financial" in cat_str.lower():
                        final_map[fname] = DocumentType.FINANCIALS
                    elif "rent" in cat_str.lower():
                         final_map[fname] = DocumentType.RENT_ROLL
                    elif "lease" in cat_str.lower():
                         final_map[fname] = DocumentType.LEASES
                    elif "memo" in cat_str.lower():
                         final_map[fname] = DocumentType.OFFERING_MEMORANDUM
                    else:
                        # Keep it as None or map to a default?
                        # The caller handles missing keys or None
                        pass
                        
            return final_map
            
        except Exception as e:
            logger.error(f"Error in batch classification: {str(e)}")
            return {}