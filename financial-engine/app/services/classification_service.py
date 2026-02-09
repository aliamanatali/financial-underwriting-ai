import logging
import json
import io
import asyncio
from typing import Optional, List, Dict, Tuple, Any
from PyPDF2 import PdfReader
from app.models.schemas import DocumentType
from app.services.gemini_client import GeminiClient
from app.services.batch_logging_service import BatchLoggingService

logger = logging.getLogger(__name__)

class ClassificationService:
    """
    Service for classifying documents into standard DocumentTypes using Gemini.
    Uses content-based classification by analyzing first 3 and last 3 pages.
    """
    
    def __init__(self, gemini_service: GeminiClient, batch_logging_service: Optional[BatchLoggingService] = None):
        self.gemini_service = gemini_service
        self.batch_logging_service = batch_logging_service

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

    async def _extract_text_with_ocr(self, content: bytes, filename: str) -> str:
        """
        Extract text from the document using Gemini Vision (OCR) as a fallback.
        This is used when standard text extraction fails (e.g., scanned PDFs).
        """
        try:
            logger.info(f"Attempting OCR with Gemini Vision for {filename}")
            
            prompt = """
            You are a helpful assistant that extracts text from documents.
            Please extract the text from this document.
            Focus on identifying information that would help classify the document type,
            such as document titles, headers, dates, and key financial terminology.
            Return a summary of the textual content found.
            """
            
            # Use the fast model for efficiency
            response = await self.gemini_service.generate_content_async(
                prompt=prompt,
                pdf_data=content,
                use_fast_model=True
            )
            
            return response
            
        except Exception as e:
            logger.error(f"OCR extraction failed for {filename}: {str(e)}")
            return ""

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
            extraction_method = "Unknown"
            
            if content:
                # Check if it's a PDF
                if filename.lower().endswith('.pdf'):
                    extraction_method = "PyPDF2"
                    extracted_content, total_pages = self._extract_pdf_pages(content)
                    logger.info(f"Extracted content from {total_pages} pages of {filename}")
                else:
                    # For non-PDF files, use content_preview or try to decode
                    try:
                        extraction_method = "utf-8 decode"
                        extracted_content = content.decode('utf-8', errors='ignore')[:2000]
                    except:
                        extraction_method = "content_preview fallback"
                        extracted_content = content_preview
            else:
                extraction_method = "content_preview only"
                extracted_content = content_preview
            
            # If we have insufficient content, try OCR fallback for PDFs/images
            if (not extracted_content or len(extracted_content.strip()) < 50) and content:
                # Check if it's a file type we can try OCR on (PDF or images)
                # GeminiClient handles the mime type detection usually, or defaults to PDF
                # We'll try it if we have content bytes
                logger.info(f"Insufficient text extracted from {filename}. Attempting fallback to Gemini Vision OCR.")
                ocr_text = await self._extract_text_with_ocr(content, filename)
                
                if ocr_text and len(ocr_text.strip()) >= 50:
                    extracted_content = ocr_text
                    extraction_method = "Gemini Vision OCR"
                    logger.info(f"Successfully extracted {len(extracted_content)} chars via OCR for {filename}")
            
            # If we still have no content, fall back to filename-based classification
            if not extracted_content or len(extracted_content.strip()) < 50:
                content_len = len(extracted_content.strip()) if extracted_content else 0
                content_display = f'"{extracted_content}"' if extracted_content else "EMPTY STRING"
                logger.warning(
                    f"Insufficient content for {filename} (Length: {content_len}, Method: {extraction_method}). "
                    f"Content: {content_display}. Using filename-based classification"
                )
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
            - {DocumentType.DISCLOSURES.value}: Environmental reports, Phase I/II, PCA, inspection reports, purchase and sale agreements (PSA), management agreements, contracts
            - {DocumentType.TAX_BILLS.value}: Property tax bills, tax returns, assessor documents
            - {DocumentType.UTILITIES.value}: Utility bills (water, electric, gas, sewer, trash)
            - {DocumentType.IMAGES.value}: Photos, images, scanned documents
            
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
                    if self.batch_logging_service:
                        self.batch_logging_service.log_classification(filename, doc_type.value, 1.0, "success")
                    return doc_type
            
            # Try partial matches if exact match fails
            matched_type = None
            if "financial" in result.lower():
                matched_type = DocumentType.FINANCIALS
            elif "rent" in result.lower() and "roll" in result.lower():
                matched_type = DocumentType.RENT_ROLL
            elif "offering" in result.lower() or "memorandum" in result.lower():
                matched_type = DocumentType.OFFERING_MEMORANDUM
            elif "lease" in result.lower():
                matched_type = DocumentType.LEASES
            elif "tax" in result.lower():
                matched_type = DocumentType.TAX_BILLS
            elif "utility" in result.lower() or "utilities" in result.lower():
                matched_type = DocumentType.UTILITIES
            elif "plan" in result.lower() or "permit" in result.lower():
                matched_type = DocumentType.BUILDING_PLANS_PERMITS
            elif "disclosure" in result.lower() or "environmental" in result.lower():
                matched_type = DocumentType.DISCLOSURES
            elif "image" in result.lower() or "photo" in result.lower():
                matched_type = DocumentType.IMAGES
            
            if matched_type:
                if self.batch_logging_service:
                    self.batch_logging_service.log_classification(filename, matched_type.value, 0.8, "success_partial")
                return matched_type
            
            logger.info(f"LLM could not confidently classify '{filename}' (Result: {result}). Defaults to Unknown.")
            
            if self.batch_logging_service:
                self.batch_logging_service.log_classification(filename, "Unknown", 0.0, "low_confidence")
            
            return None

        except Exception as e:
            logger.error(f"Error classifying file {filename}: {str(e)}")
            if self.batch_logging_service:
                self.batch_logging_service.log_error(filename, "classify_file", str(e))
            return None

    async def _classify_by_filename(self, filename: str) -> Optional[DocumentType]:
        """
        Fallback classification based on filename keywords.
        """
        filename_lower = filename.lower()
        
        if "rent roll" in filename_lower or "rentroll" in filename_lower or "rent_roll" in filename_lower:
            return DocumentType.RENT_ROLL
        if "t12" in filename_lower or "trailing 12" in filename_lower or "p&l" in filename_lower or "profit & loss" in filename_lower or "income statement" in filename_lower:
            return DocumentType.FINANCIALS
        if "om" in filename_lower or "offering memorandum" in filename_lower or "flyer" in filename_lower or "offering_memorandum" in filename_lower:
            return DocumentType.OFFERING_MEMORANDUM
        if "lease" in filename_lower and ("agreement" in filename_lower or "contract" in filename_lower):
            return DocumentType.LEASES
        if "tax" in filename_lower and "bill" in filename_lower:
            return DocumentType.TAX_BILLS
        if "utility" in filename_lower or "utilities" in filename_lower:
            return DocumentType.UTILITIES
        if "plan" in filename_lower or "permit" in filename_lower:
            return DocumentType.BUILDING_PLANS_PERMITS
        if "disclosure" in filename_lower or "environmental" in filename_lower or "psa" in filename_lower or "purchase and sale" in filename_lower or "mgmt" in filename_lower or "management agreement" in filename_lower:
            return DocumentType.DISCLOSURES
        
        return None

    async def classify_files_batch(
        self,
        files: List[Tuple[str, Optional[bytes]]] = None,
        filenames: List[str] = None,
        progress_service: Any = None,
        task_id: str = None,
        progress_start: int = 20,
        progress_end: int = 90
    ) -> Dict[str, DocumentType]:
        """
        Classify a batch of files using content-based analysis.
        
        Args:
            files: List of tuples (filename, content_bytes) - preferred method
            filenames: List of filenames only - fallback to filename-based classification
            progress_service: Optional service to update progress
            task_id: Optional task ID for progress updates
            progress_start: Starting progress percentage
            progress_end: Ending progress percentage
            
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
            total_files = len(files)
            completed_count = 0
            
            # Helper to wrap classification with progress update
            async def classify_with_progress(filename, content):
                nonlocal completed_count
                try:
                    res = await self.classify_file(filename, content=content)
                except Exception as e:
                    logger.error(f"Error classifying {filename}: {e}")
                    res = None
                
                completed_count += 1
                
                if progress_service and task_id:
                    pct_range = progress_end - progress_start
                    if total_files > 0:
                        current_pct = progress_start + int((completed_count / total_files) * pct_range)
                    else:
                        current_pct = progress_end
                        
                    await progress_service.update_progress(
                        task_id,
                        current_pct,
                        f"Classified {completed_count}/{total_files} files...",
                        details={
                            "current_file": filename,
                            "status": "classifying",
                            "completed": completed_count,
                            "total": total_files
                        }
                    )
                return res

            # Process files in parallel
            tasks = []
            for filename, content in files:
                tasks.append(classify_with_progress(filename, content))
            
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
            - {DocumentType.IMAGES.value}
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
            
            # Clean response using robust extraction
            cleaned_text = response.strip()
            
            # Use regex to find JSON content between ```json and ``` or ``` and ```
            import re
            match = re.search(r"```json\s*([\s\S]*?)\s*```", cleaned_text, re.DOTALL)
            if not match:
                match = re.search(r"```\s*([\s\S]*?)\s*```", cleaned_text, re.DOTALL)
            
            if match:
                cleaned_text = match.group(1).strip()
            else:
                # Fallback: look for outer object brackets
                start_idx = cleaned_text.find("{")
                end_idx = cleaned_text.rfind("}")
                if start_idx != -1 and end_idx != -1 and end_idx > start_idx:
                    cleaned_text = cleaned_text[start_idx:end_idx+1]
            
            results_dict = json.loads(cleaned_text)
            
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
                    elif "image" in cat_str.lower() or "photo" in cat_str.lower():
                         final_map[fname] = DocumentType.IMAGES
                    else:
                        if self.batch_logging_service:
                             self.batch_logging_service.log_classification(fname, cat_str, 0.0, "unknown_category")
                        pass

                if self.batch_logging_service and fname in final_map:
                     self.batch_logging_service.log_classification(fname, final_map[fname].value, 1.0, "batch_success")
                        
            return final_map
            
        except Exception as e:
            logger.error(f"Error in batch classification: {str(e)}")
            if self.batch_logging_service:
                self.batch_logging_service.log_error("batch", "classify_files_batch", str(e))
            return {}