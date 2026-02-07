"""
Multi-Document Extraction Service
Handles extraction of financial data from PDFs and Excel files in deal packages.
"""

import io
import logging
import json
import asyncio
from typing import List, Dict, Any, Optional
import openpyxl
from openpyxl.worksheet.worksheet import Worksheet
from google import genai
from tenacity import AsyncRetrying, stop_after_attempt, wait_exponential, retry_if_exception_type
from google.genai import errors as genai_errors
from google.genai import types
from app.models.schemas import (
    NormalizedDataItem, DocumentType, CategoryGroup, DataClassification,
    ExpenseCategory, OMProformaTable, RentRollItem
)
from app.services.batch_logging_service import BatchLoggingService
from app.services.ingestion_service import IngestionService

logger = logging.getLogger(__name__)


class MultiDocumentExtractionService:
    """Service for extracting and normalizing financial data from multiple document types."""
    
    # Standard expense categories for normalization
    # Explicitly map MARKETING to Advertising & Marketing if needed, but enum handles values.
    # We ensure "Advertising & Marketing" is used instead of just "Marketing".
    STANDARD_CATEGORIES = [e.value for e in ExpenseCategory]
    
    def __init__(self, gemini_service=None, batch_logging_service: Optional[BatchLoggingService] = None):
        """Initialize the extraction service with optional Gemini service."""
        self.gemini_service = gemini_service
        self.batch_logging_service = batch_logging_service
        self.ingestion_service = IngestionService()
    
    async def process_rent_roll_documents(
        self,
        documents: List[Dict[str, Any]],
        progress_service: Any = None,
        task_id: Optional[str] = None,
        progress_start: int = 20,
        progress_end: int = 30,
        initial_completed_files: List[str] = None
    ) -> (List[RentRollItem], List[str]):
        """
        Process multiple rent roll documents and return a list of RentRollItems.
        Does not perform deduplication/synthesis; that happens in SynthesisService.
        """
        all_rent_roll_items = []
        
        # Progress tracking variables
        completed_count = 0
        total_count = len(documents)
        active_files = set()
        completed_files = set(initial_completed_files or [])

        async def update_progress(filename: str, status: str):
            nonlocal completed_count
            
            if status == "started":
                active_files.add(filename)
            elif status in ["completed", "failed"]:
                if filename in active_files:
                    active_files.remove(filename)
                completed_count += 1
                completed_files.add(filename)
            
            if progress_service and task_id:
                # Calculate percentage: Map 0..total to progress_start..progress_end
                pct_range = progress_end - progress_start
                if total_count > 0:
                    current_pct = progress_start + int((completed_count / total_count) * pct_range)
                else:
                    current_pct = progress_start
                
                # Calculate cumulative stats
                initial_count = len(initial_completed_files or [])
                cumulative_index = initial_count + completed_count
                cumulative_total = initial_count + total_count
                
                # Determine message
                if status == "started":
                    msg = f"Processing {filename}..."
                else:
                    msg = f"Processed {cumulative_index}/{cumulative_total} documents"

                await progress_service.update_progress(
                    task_id,
                    current_pct,
                    msg,
                    details={
                        "current_file": filename,
                        "document_category": "Rent Roll",
                        "file_index": cumulative_index,
                        "total_files": cumulative_total,
                        "active_files": list(active_files),
                        "completed_files": list(completed_files),
                        "status": "processing"
                    }
                )

        for doc in documents:
            file_content = doc.get("content")
            filename = doc.get("filename", "unknown")
            file_type = doc.get("type", "").lower()
            
            await update_progress(filename, "started")

            # Estimate total units if possible or pass 0
            # Ideally we get this from property meta but we might not have it yet.
            # Passing 0 usually works for extraction prompts.
            total_units = 0
            
            try:
                items = []
                if file_type in ["xlsx", "xls", "excel"] or filename.endswith((".xlsx", ".xls")):
                    items = await self.ingestion_service.extract_rent_roll_from_excel(
                        file_content, total_units=total_units, filename=filename
                    )
                elif file_type in ["pdf", "visual"] or filename.endswith((".pdf", ".png", ".jpg")):
                    items = await self.ingestion_service.extract_rent_roll_from_pdf(
                        file_content, total_units=total_units, filename=filename
                    )
                
                if items:
                    # FIX: Append with source file info to allow deduplication later
                    # (Ingestion service already sets source_file, but just in case)
                    for item in items:
                        if not item.source_file:
                            item.source_file = filename
                    all_rent_roll_items.extend(items)
                    logger.info(f"Extracted {len(items)} rent roll items from {filename}")
                
                await update_progress(filename, "completed")

            except Exception as e:
                logger.error(f"Error processing Rent Roll {filename}: {e}")
                await update_progress(filename, "failed")
        
        # Deduplicate Rent Roll based on unit numbers
        # If we have multiple Rent Roll files, we should prioritize the one with the most data
        # or merge unique units. For simplicity and robustness, we'll deduplicate by Unit Number.
        # Prefer the first occurrence (or last? usually the last processed file might be better/worse).
        # Actually, SynthesisService handles the master rent roll creation logic.
        # But `process_rent_roll_documents` returns the RAW list.
        # It's better to let SynthesisService handle the logic, BUT we should ensure we don't just sum them up blindly.
        # However, the current flow returns `all_rent_roll_items` which is then passed to `synthesis_service.build_master_rent_roll`.
        # So we are good here, assuming SynthesisService does its job.
        
        return all_rent_roll_items, list(completed_files)

    async def extract_from_csv(self, file_content: bytes, filename: str) -> List[Dict[str, Any]]:
        """
        Extract aggregated financial data from CSV files.
        Returns a single summary entry per document.
        
        Args:
            file_content: Raw bytes of the CSV file
            filename: Name of the file for reference
            
        Returns:
            List with a single dictionary containing aggregated expense data
        """
        import csv
        
        try:
            logger.info(f"Processing CSV file: {filename}")
            
            # Decode content
            try:
                text_content = file_content.decode('utf-8')
            except UnicodeDecodeError:
                text_content = file_content.decode('latin-1')
                
            f = io.StringIO(text_content)
            reader = csv.reader(f)
            all_rows = list(reader)
            
            if not all_rows:
                logger.warning(f"No rows found in {filename}")
                return []
            
            # Check for header
            first_row = all_rows[0] if all_rows else []
            skip_first_row = False
            if first_row:
                first_row_str = " ".join([str(cell).lower() for cell in first_row])
                if any(keyword in first_row_str for keyword in ["id", "description", "category", "amount", "date", "notes", "expense", "item"]):
                    skip_first_row = True
            
            # Aggregate data
            start_row = 1 if skip_first_row else 0
            total_amount = 0.0
            row_count = 0
            categories = set()
            
            for row in all_rows[start_row:]:
                if not row:
                    continue
                
                # Find category
                for cell in row:
                    if cell and len(str(cell).strip()) > 1:
                        # Check if it's NOT a number
                        try:
                            float(str(cell).replace(',', '').replace('$', ''))
                        except ValueError:
                            categories.add(str(cell).strip())
                            break
                
                # Find amount
                for cell in row:
                    if cell:
                        try:
                            val = float(str(cell).replace(',', '').replace('$', ''))
                            if val > 0:
                                total_amount += val
                                row_count += 1
                                break
                        except ValueError:
                            continue
            
            if row_count == 0:
                logger.warning(f"No valid data rows found in {filename}")
                return []
                
            # Determine document type
            doc_type = "Financial Statement"
            if "t12" in filename.lower():
                doc_type = "T12 Statement"
            elif "rent" in filename.lower() and "roll" in filename.lower():
                doc_type = "Rent Roll"
            elif "p&l" in filename.lower() or "pl" in filename.lower():
                doc_type = "P&L Statement"
            
            entry_type = "expense"
            if "rent" in filename.lower() and "roll" in filename.lower():
                entry_type = "property_info"
            
            aggregated_entry = {
                "raw_text": f"{doc_type} - {filename}",
                "amount": total_amount,
                "source_document": filename,
                "row_count": row_count,
                "type": entry_type,
                "categories_found": list(categories)[:5]
            }
            
            logger.info(f"Extracted aggregated data from CSV {filename}: {row_count} rows, total amount: ${total_amount:,.2f}")
            return [aggregated_entry]

        except Exception as e:
            logger.error(f"Error extracting from CSV file {filename}: {str(e)}", exc_info=True)
            if self.batch_logging_service:
                self.batch_logging_service.log_error(filename, "extract_from_csv", str(e))
            raise

    async def extract_from_excel(self, file_content: bytes, filename: str) -> List[Dict[str, Any]]:
        """
        Extract aggregated financial data from Excel files (T12, P&L, Rent Roll, etc.).
        Supports .xlsx via openpyxl and .xls via pandas/xlrd.
        Returns a single summary entry per document instead of individual rows.
        
        Args:
            file_content: Raw bytes of the Excel file
            filename: Name of the file for reference
            
        Returns:
            List with a single dictionary containing aggregated expense data
        """
        import asyncio
        loop = asyncio.get_event_loop()
        try:
            return await loop.run_in_executor(None, self._extract_from_excel_sync, file_content, filename)
        except Exception as e:
            logger.error(f"Error extracting from Excel file {filename}: {str(e)}", exc_info=True)
            if self.batch_logging_service:
                self.batch_logging_service.log_error(filename, "extract_from_excel", str(e))
            raise

    def _extract_from_excel_sync(self, file_content: bytes, filename: str) -> List[Dict[str, Any]]:
        """Synchronous implementation of Excel extraction for thread pool execution."""
        total_amount = 0.0
        row_count = 0
        categories = set()
        
        try:
            # Check file extension to decide extraction method
            is_legacy_xls = filename.lower().endswith('.xls')
            
            if is_legacy_xls:
                import pandas as pd
                logger.info(f"Processing legacy Excel file (.xls): {filename}")
                try:
                    # Use pandas with xlrd engine for .xls files
                    df = pd.read_excel(io.BytesIO(file_content), header=None, engine='xlrd')
                    # Iterate rows
                    for _, row in df.iterrows():
                        # Find category/description (first non-numeric string)
                        for cell in row:
                            if pd.notna(cell) and isinstance(cell, str) and len(str(cell).strip()) > 1:
                                try:
                                    float(cell)
                                except (ValueError, TypeError):
                                    categories.add(str(cell).strip())
                                    break
                        
                        # Find and sum amounts (first positive number)
                        for cell in row:
                            if pd.notna(cell) and isinstance(cell, (int, float)) and cell > 0:
                                total_amount += float(cell)
                                row_count += 1
                                break
                    
                except ImportError:
                    logger.error("xlrd not installed, cannot process .xls files")
                    raise Exception("xlrd library required for .xls support")
                except Exception as e:
                    logger.error(f"Pandas .xls extraction failed: {e}")
                    raise
            else:
                # Default .xlsx handling with openpyxl (preferred for memory efficiency)
                workbook = openpyxl.load_workbook(io.BytesIO(file_content), data_only=True)
                sheet = workbook.active
                
                logger.info(f"Processing Excel file: {filename}, sheet: {sheet.title}")
                
                # Get all rows
                all_rows = list(sheet.iter_rows(min_row=1, values_only=True))
                
                if not all_rows:
                    logger.warning(f"No rows found in {filename}")
                    return []
                
                # Check if first row looks like a header
                first_row = all_rows[0] if all_rows else []
                skip_first_row = False
                if first_row:
                    first_row_str = [str(cell).lower() if cell else "" for cell in first_row]
                    if any(keyword in " ".join(first_row_str) for keyword in ["id", "description", "category", "amount", "date", "notes", "expense", "item"]):
                        skip_first_row = True
                        logger.info(f"Detected header row: {first_row[:6]}")
                
                # Aggregate all data
                start_row = 2 if skip_first_row else 1
                
                for row_idx, row in enumerate(all_rows[start_row-1:], start=start_row):
                    if not row or len(row) < 2:
                        continue
                    
                    # Find category/description
                    for cell in row:
                        if cell and isinstance(cell, str) and len(str(cell).strip()) > 1:
                            try:
                                float(cell)
                            except (ValueError, TypeError):
                                categories.add(str(cell).strip())
                                break
                    
                    # Find and sum amounts
                    for cell in row:
                        if isinstance(cell, (int, float)) and cell > 0:
                            total_amount += float(cell)
                            row_count += 1
                            break
            
            if row_count == 0:
                logger.warning(f"No valid data rows found in {filename}")
                return []
            
            # Determine document type from filename
            doc_type = "Financial Statement"
            if "t12" in filename.lower():
                doc_type = "T12 Statement"
            elif "rent" in filename.lower() and "roll" in filename.lower():
                doc_type = "Rent Roll"
            elif "p&l" in filename.lower() or "pl" in filename.lower():
                doc_type = "P&L Statement"
            
            # Create a single aggregated entry
            # Determine type based on document type
            entry_type = "expense"  # default
            if "rent" in filename.lower() and "roll" in filename.lower():
                entry_type = "property_info"
            elif "t12" in filename.lower() or "statement" in filename.lower():
                entry_type = "expense"
            
            aggregated_entry = {
                "raw_text": f"{doc_type} - {filename}",
                "amount": total_amount,
                "source_document": filename,
                "row_count": row_count,
                "type": entry_type,
                "categories_found": list(categories)[:5]  # Keep first 5 categories as sample
            }
            
            logger.info(f"Extracted aggregated data from {filename}: {row_count} rows, total amount: ${total_amount:,.2f}")
            
            return [aggregated_entry]  # Return single entry instead of multiple
            
        except Exception as e:
            logger.error(f"Error inside sync Excel extraction for {filename}: {str(e)}", exc_info=True)
            raise
    
    async def extract_from_visual_document(self, file_content: bytes, filename: str, mime_type: str = "application/pdf") -> List[Dict[str, Any]]:
        """
        Extract expense line items from visual files (PDFs, Images) using Gemini Vision API.
        
        Args:
            file_content: Raw bytes of the file
            filename: Name of the file for reference
            mime_type: MIME type of the file (e.g., "application/pdf", "image/png")
            
        Returns:
            List of dictionaries containing raw expense data
        """
        if not self.gemini_service:
            logger.warning("Gemini service not available for visual extraction")
            return []
        
        try:
            logger.info(f"Starting visual extraction for {filename} ({len(file_content)} bytes, type: {mime_type})")
            
            # Upload file to Gemini using the File API
            import tempfile
            import os
            
            # Determine extension from mime type or filename
            ext = ".pdf"
            if "image" in mime_type:
                if "png" in mime_type: ext = ".png"
                elif "jpeg" in mime_type or "jpg" in mime_type: ext = ".jpg"
            elif filename:
                 _, ext = os.path.splitext(filename)
            
            # Create a temporary file
            with tempfile.NamedTemporaryFile(delete=False, suffix=ext) as tmp_file:
                tmp_file.write(file_content)
                tmp_path = tmp_file.name
            
            try:
                # Read file content for direct processing (new API doesn't require file upload)
                # Instead, we'll pass the file content directly
                with open(tmp_path, 'rb') as f:
                    file_bytes = f.read()
                
                logger.info(f"Processing file with Gemini: {filename} ({mime_type})")

                prompt = """
                Analyze this financial document (T12, P&L, Income Statement, Tax Bill, Utility Bill, Lease Agreement, Offering Memorandum, or Disclosure) and extract ALL financial items.
                
                You must distinguish between:
                1. Revenue / Income (e.g., Rent, Reimbursements, Other Income)
                2. Operating Expenses (e.g., Taxes, Insurance, R&M, Management, Utilities)
                3. Property Characteristics (e.g., "Year Built", "Roof Age", "Unit Count", "Rentable Sq Ft")
                4. Capital Expenditures (e.g., "New Roof", "HVAC Replacement")
                
                CRITICAL RULES TO AVOID ERRORS:
                
                1. PAST DUE / RECEIVABLES HANDLING:
                   - "Past Due", "Delinquent Rent", "Arrears", "Outstanding Balance" should be type: "receivable" NOT "revenue"
                   - These represent uncollected amounts, not actual income
                   - Only extract actual rent payments as revenue
                
                2. REVENUE STREAM SEPARATION:
                   - "Rent", "Monthly Rent", "Rental Income" → type: "revenue", subtype: "rent"
                   - "Late Fee", "Late Charge", "Penalty" → type: "revenue", subtype: "late_fee"
                   - "Laundry Income", "Parking Income", "Pet Fee" → type: "revenue", subtype: "other_income"
                   - "Check Return Fee", "NSF Fee" → type: "revenue", subtype: "other_income"
                   - "Utility Reimbursement", "CAM Reimbursement" → type: "revenue", subtype: "reimbursement"
                
                3. CAPITAL VS OPERATING EXPENSES:
                   - Capital items (>$5,000, extends useful life): "New Roof", "HVAC Replacement", "Electrical Upgrade", "Major Renovation" → type: "capex"
                   - Operating items: "Roof Repair", "HVAC Maintenance", "Minor Repairs" → type: "expense"
                   - Permit fees for capital work → type: "capex"
                   - Permit fees for repairs → type: "expense"
                
                4. NO DUPLICATE SCENARIOS: If the document shows multiple columns (e.g., "Current" vs "Pro Forma"), extract ONLY the "Current" or "Actual" or "T-12" column.
                
                5. NO SISTER PROPERTIES: Extract ONLY expenses for the subject property if identifiable.
                
                6. NO DOUBLE COUNTING: Do NOT extract "Total" or "Subtotal" lines if you are also extracting individual line items.
                
                7. NO ASSESSED VALUES: Do NOT extract "Assessed Value" as a Tax Expense. Only extract actual tax amounts due.

                8. IGNORE INSURANCE LIMITS:
                   - Do NOT extract "Aggregate", "Per Claim", "Limit of Liability", "Per Occurrence", "Medical Expenses", "Deductible".
                   - These are coverage limits, NOT the premium amount.
                   - Only extract the "Premium" or "Total Premium" amount.
                
                For each item, provide:
                1. The exact text/description as it appears in the document
                2. The amount (annual or monthly) if applicable
                3. The item type: "revenue", "expense", "property_info", "capex", "receivable"
                4. The subtype (for revenue items): "rent", "late_fee", "other_income", "reimbursement"
                5. The expense year (if identifiable, e.g. 2022, 2023)
                6. The page number where this item is found
                7. The bounding box of the area containing this item
                
                Return the data as a JSON array with this structure:
                [
                    {
                        "raw_text": "Exact description",
                        "amount": 12345.67, // or null
                        "period": "annual" or "monthly" or "one-time",
                        "type": "revenue", // or "expense", "property_info", "capex", "receivable"
                        "subtype": "rent", // for revenue: "rent", "late_fee", "other_income", "reimbursement"; optional for others
                        "expense_year": 2023, // Integer year if found, null otherwise
                        "page_number": 1, // Integer, 1-based page number
                        "bbox": [ymin, xmin, ymax, xmax] // Array of 4 integers, normalized coordinates 0-1000
                    }
                ]
                
                IMPORTANT:
                - Do NOT categorize Revenue items (like "Rental Income", "Lease Payments") as Expenses
                - Do NOT categorize Property Characteristics (like "Year Built") as Expenses
                - Do NOT categorize Past Due amounts as Revenue - they are Receivables
                - Separate late fees from rent
                - If the document is a Rent Roll or Lease, capture the Rental Income as type: "revenue", subtype: "rent"
                
                Return ONLY the JSON array, no additional text or explanation.
                """
                
                # Use gemini_service to generate content with file
                # Create parts for multimodal input
                parts = [
                    types.Part.from_bytes(data=file_bytes, mime_type=mime_type),
                    types.Part.from_text(text=prompt)
                ]
                
                # Get the client from gemini_service
                client = self.gemini_service.client
                model_name = self.gemini_service.model_name
                
                try:
                    # Retry logic for 500 errors
                    async for attempt in AsyncRetrying(
                        stop=stop_after_attempt(3),
                        wait=wait_exponential(multiplier=1, min=2, max=10),
                        retry=retry_if_exception_type((genai_errors.ServerError, genai_errors.APIError)),
                        reraise=True
                    ):
                        with attempt:
                            response = await asyncio.wait_for(
                                client.aio.models.generate_content(
                                    model=model_name,
                                    contents=parts,
                                    config=types.GenerateContentConfig(temperature=0.0)
                                ),
                                timeout=120.0
                            )
                except asyncio.TimeoutError:
                    logger.error(f"Gemini visual extraction timed out for {filename}")
                    return [{
                        "raw_text": f"Document - {filename} (Extraction timed out)",
                        "amount": 0.0,
                        "source_document": filename,
                        "error": "Timeout"
                    }]
                except (genai_errors.ServerError, genai_errors.APIError) as e:
                    logger.error(f"Gemini visual extraction failed after retries for {filename}: {e}")
                    return [{
                        "raw_text": f"Document - {filename} (Gemini Error: {str(e)})",
                        "amount": 0.0,
                        "source_document": filename,
                        "error": str(e)
                    }]
                
                # Parse JSON response
                if not response.text:
                    logger.warning(f"Gemini returned empty response for {filename}")
                    return []
                    
                response_text = response.text.strip()
                logger.info(f"Gemini response for {filename}: {response_text[:200]}...")
                
                # Remove markdown code blocks if present
                if response_text.startswith("```json"):
                    response_text = response_text[7:]
                if response_text.startswith("```"):
                    response_text = response_text[3:]
                if response_text.endswith("```"):
                    response_text = response_text[:-3]
                
                response_text = response_text.strip()
                
                expenses_data = json.loads(response_text)
                
                # Validate that we got a list
                if not isinstance(expenses_data, list):
                    logger.error(f"Expected list from Gemini, got {type(expenses_data)}")
                    return []
                
                # Add source document to each item
                for expense in expenses_data:
                    expense["source_document"] = filename
                    
                    # Handle cases where amount is None (extracted as null)
                    if expense.get("amount") is None:
                        expense["amount"] = 0.0
                        
                    # Convert monthly to annual if needed
                    if expense.get("period") == "monthly":
                        try:
                            expense["amount"] = float(expense["amount"]) * 12
                        except (ValueError, TypeError):
                            logger.warning(f"Could not convert amount to float for monthly calculation: {expense.get('amount')}")
                            expense["amount"] = 0.0
                
                logger.info(f"Extracted {len(expenses_data)} expense items from {filename}")
                return expenses_data
                
            finally:
                # Clean up temporary file
                import os
                if os.path.exists(tmp_path):
                    os.unlink(tmp_path)
            
        except json.JSONDecodeError as e:
            logger.error(f"JSON parsing error for {filename}: {str(e)}", exc_info=True)
            logger.error(f"Response text was: {response_text if 'response_text' in locals() else 'N/A'}")
            # Return placeholder instead of raising
            return [{
                "raw_text": f"Document - {filename} (JSON parsing error)",
                "amount": 0.0,
                "source_document": filename,
                "error": str(e)
            }]
        except Exception as e:
            logger.error(f"Error extracting from file {filename}: {str(e)}", exc_info=True)
            if self.batch_logging_service:
                self.batch_logging_service.log_error(filename, "extract_from_visual_document", str(e))
            # Return placeholder instead of raising
            return [{
                "raw_text": f"Document - {filename} (Extraction error: {str(e)[:100]})",
                "amount": 0.0,
                "source_document": filename,
                "error": str(e)
            }]

    async def extract_om_proforma_from_pdf(self, file_content: bytes, filename: str) -> List[OMProformaTable]:
        """
        Extracts the 'Proforma' or 'Pro Forma' table from the OM PDF.
        """
        if not self.gemini_service:
            logger.warning("Gemini service not available for OM Proforma extraction")
            return []

        try:
            logger.info(f"Starting OM Proforma extraction for {filename}")

            prompt = """
            Analyze this Offering Memorandum and find the "Proforma" or "Pro Forma" table(s).
            These tables typically list Income, Expenses, and NOI for different scenarios like "Stabilized Rent" and "Market Rents".

            Your task is to:
            1.  Identify each Proforma table/scenario.
            2.  For each table, extract the scenario name (e.g., "Proforma at Stabilized Rent").
            3.  Extract all financial rows within that table, including "Annual", "Monthly", and "Per Unit" values.
            4.  Extract the summary data at the bottom of each table: "Purchase Price", "CAP Rate", and "GRM".

            Return the data as a JSON array of objects, where each object represents one proforma table.
            The JSON structure must follow this format:
            [
                {
                    "scenario_name": "Proforma at Stabilized Rent",
                    "rows": [
                        {"row_name": "Gross Potential Market Rent", "annual": 1080000, "monthly": 90000, "per_unit": 33750},
                        {"row_name": "Vacancy", "annual": -46191, "monthly": -3849, "per_unit": -1443, "percentage": 0.05},
                        ...
                    ],
                    "purchase_price": 9440000,
                    "cap_rate": 0.0559,
                    "grm": 10.22
                },
                ...
            ]

            CRITICAL:
            - Preserve the exact row names.
            - Return ONLY the JSON array.
            """

            # Since this is a specialized extraction, we'll use the vision model directly
            import tempfile
            import os

            with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp_file:
                tmp_file.write(file_content)
                tmp_path = tmp_file.name
            
            try:
                # Read file content for direct processing
                with open(tmp_path, 'rb') as f:
                    file_bytes = f.read()
                
                logger.info(f"Processing OM file with Gemini: {filename}")
                
                # Create parts for multimodal input
                parts = [
                    types.Part.from_bytes(data=file_bytes, mime_type="application/pdf"),
                    types.Part.from_text(text=prompt)
                ]
                
                # Get the client from gemini_service
                client = self.gemini_service.client
                model_name = self.gemini_service.model_name
                
                try:
                    # Retry logic for 500 errors
                    async for attempt in AsyncRetrying(
                        stop=stop_after_attempt(3),
                        wait=wait_exponential(multiplier=1, min=2, max=10),
                        retry=retry_if_exception_type((genai_errors.ServerError, genai_errors.APIError)),
                        reraise=True
                    ):
                        with attempt:
                            response = await asyncio.wait_for(
                                client.aio.models.generate_content(
                                    model=model_name,
                                    contents=parts,
                                    config=types.GenerateContentConfig(temperature=0.0)
                                ),
                                timeout=120.0
                            )
                except asyncio.TimeoutError:
                    logger.error(f"Gemini OM extraction timed out for {filename}")
                    return []
                except (genai_errors.ServerError, genai_errors.APIError) as e:
                    logger.error(f"Gemini OM extraction failed after retries for {filename}: {e}")
                    return []
                
                if not response.text:
                    logger.warning(f"Gemini returned empty response for OM {filename}")
                    return []

                response_text = response.text.strip()
                if response_text.startswith("```json"):
                    response_text = response_text[7:]
                if response_text.endswith("```"):
                    response_text = response_text[:-3]
                
                proforma_data = json.loads(response_text)

                if not isinstance(proforma_data, list):
                    logger.error(f"Expected a list for OM Proforma, but got {type(proforma_data)}")
                    return []

                return [OMProformaTable(**item) for item in proforma_data]

            finally:
                if os.path.exists(tmp_path):
                    os.unlink(tmp_path)

        except json.JSONDecodeError as e:
            logger.error(f"JSON parsing error for OM Proforma in {filename}: {str(e)}", exc_info=True)
            return []
        except Exception as e:
            logger.error(f"Error extracting OM Proforma from {filename}: {str(e)}", exc_info=True)
            return []
    
    def _validate_and_fix_extraction(self, expenses: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Post-process extracted items to fix common categorization errors.
        """
        fixed_expenses = []
        
        for exp in expenses:
            raw_text = exp.get("raw_text", "").lower()
            item_type = exp.get("type", "expense")
            
            # Fix 0: Blacklist Tuition/Student Financial Aid items
            # These are personal financial documents often mixed in with property docs
            blacklist_keywords = ["tuition", "scholarship", "financial aid", "student services", "semester", "undergraduate resident"]
            if any(keyword in raw_text for keyword in blacklist_keywords):
                logger.warning(f"Blacklisted item detected and ignored: '{exp.get('raw_text')}'")
                exp["type"] = "other"
                exp["subtype"] = "tuition_ignored"
                # We do not append to fixed_expenses if we want to delete it,
                # but the instruction says "set its type to 'other' ... to ensure it is effectively deleted or ignored downstream."
                # However, usually _validate_and_fix_extraction returns the list to be used.
                # If I change type to "other", it might still be processed.
                # Let's keep it in but mark it as ignored so downstream normalization filters it out or maps it to 'Other'.
            
            # Fix 1: Past Due should NEVER be revenue
            elif any(keyword in raw_text for keyword in ["past due", "delinquent", "arrears", "outstanding balance", "overdue"]):
                if item_type == "revenue":
                    logger.warning(f"Fixing incorrect categorization: '{exp.get('raw_text')}' was marked as revenue, changing to receivable")
                    exp["type"] = "receivable"
                    exp["subtype"] = "past_due"
            
            # Fix 2: Late fees should be other_income, not rent
            elif any(keyword in raw_text for keyword in ["late fee", "late charge", "penalty", "nsf", "check return"]):
                if item_type == "revenue":
                    exp["subtype"] = "late_fee"
                    logger.info(f"Categorized '{exp.get('raw_text')}' as late_fee")
            
            # Fix 3: Laundry, parking, pet fees are other_income
            elif any(keyword in raw_text for keyword in ["laundry", "parking", "garage", "pet fee", "pet rent", "storage"]):
                if item_type == "revenue":
                    exp["subtype"] = "other_income"
                    logger.info(f"Categorized '{exp.get('raw_text')}' as other_income")
            
            # Fix 4: Utility reimbursements
            elif any(keyword in raw_text for keyword in ["utility reimbursement", "cam reimbursement", "reimbursement"]):
                if item_type == "revenue":
                    exp["subtype"] = "reimbursement"
                    logger.info(f"Categorized '{exp.get('raw_text')}' as reimbursement")
            
            # Fix 5: Capital expenditures (electrical upgrades, major work, elevator, retaining wall)
            elif any(keyword in raw_text for keyword in ["electrical upgrade", "new service", "panel upgrade", "major renovation", "roof replacement", "hvac replacement", "elevator modernization", "cylinder replacement", "retaining wall", "seismic", "foundation work"]):
                if item_type == "expense":
                    exp["type"] = "capex"
                    logger.info(f"Recategorized '{exp.get('raw_text')}' as capital expenditure")

            # Fix 5b: High dollar threshold heuristic for ambiguous items (e.g. > $15,000 single invoice usually CapEx)
            # This is risky without context, but for "Proposal" or "Modernization" it works.
            elif any(keyword in raw_text for keyword in ["proposal", "modernization", "installation", "replacement"]):
                amount = exp.get("amount", 0)
                if amount and amount > 5000:
                    exp["type"] = "capex"
                    logger.info(f"Recategorized '{exp.get('raw_text')}' as capital expenditure (High $ + Keyword)")
            
            # Fix 6: Permit fees for capital work
            elif "permit" in raw_text and any(keyword in raw_text for keyword in ["electrical", "upgrade", "replacement", "new"]):
                if item_type == "expense":
                    exp["type"] = "capex"
                    logger.info(f"Recategorized permit '{exp.get('raw_text')}' as capital expenditure")
            
            # Fix 7: Ensure rent has correct subtype
            elif any(keyword in raw_text for keyword in ["monthly rent", "rent", "rental income"]) and "late" not in raw_text:
                if item_type == "revenue" and not exp.get("subtype"):
                    exp["subtype"] = "rent"
            
            # Fix 8: Ignore "Total" lines to prevent double counting
            # This is critical for utility bills where line items and total are both extracted
            if "total" in raw_text and item_type == "expense":
                # Check if it's a summary line like "Total Charges" or "Total Due"
                if any(keyword in raw_text for keyword in ["total charges", "total due", "amount due", "total amount", "current charges"]):
                     # We skip adding it to fixed_expenses effectively deleting it
                     # UNLESS it's the only item extracted? No, risky.
                     # Better to mark it as ignored or separate type.
                     logger.info(f"Ignoring potential duplicate summary line: '{exp.get('raw_text')}'")
                     continue

            fixed_expenses.append(exp)
        
        return fixed_expenses
    
    async def normalize_expenses_batch(self, expenses: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Batch normalize expenses using Gemini to reduce API calls and latency.
        """
        if not expenses:
            return []
        
        # First, validate and fix common errors
        expenses = self._validate_and_fix_extraction(expenses)
            
        if not self.gemini_service:
            return [self._fallback_categorization(e) for e in expenses]

        try:
            # Prepare items for prompt
            items_payload = []
            for idx, exp in enumerate(expenses):
                items_payload.append({
                    "id": idx,
                    "text": exp.get("raw_text", ""),
                    "type": exp.get("type", "expense"),
                    "subtype": exp.get("subtype", "")
                })
            
            prompt = f"""
            You are a commercial real estate financial analyst. Map these {len(items_payload)} line items to the most appropriate standard category and group.
            
            Standard Categories:
            {chr(10).join(f"- {cat}" for cat in self.STANDARD_CATEGORIES)}
            
            Items to Process:
            {json.dumps(items_payload, indent=2)}
            
            Respond with ONLY a JSON array of objects in this exact format:
            [
                {{
                    "id": 0,  // Must match input ID
                    "category": "Exact category name from the list above",
                    "group": "Revenue" | "Operating Expense" | "Capital Expenditure" | "Property Info" | "Debt" | "Tax & Insurance" | "Other",
                    "confidence": 0.95,
                    "reasoning": "Brief explanation"
                }}
            ]
            
            CRITICAL RULES:
            - If type is "receivable", map to Group: "Other" and Category: "Accounts Receivable" (NOT revenue - these are uncollected amounts)
            - If type is "revenue" and subtype is "rent", map to Group: "Revenue" and Category: "Gross Potential Rent"
            - If type is "revenue" and subtype is "late_fee", map to Group: "Revenue" and Category: "Other Income"
            - If type is "revenue" and subtype is "other_income", map to Group: "Revenue" and Category: "Other Income"
            - If type is "revenue" and subtype is "reimbursement", map to Group: "Revenue" and Category: "Reimbursements"
            - If type is "capex", map to Group: "Capital Expenditure" and Category: "Capital Reserves"
            - Map "Purchase Price", "Asking Price", "Sale Price" to Group: "Property Info" and Category: "Purchase Price"
            - Map "Price per Unit", "Cost per Unit" to Group: "Property Info" and Category: "Price per Unit"
            - Map "Units", "Total Units", "Unit Count" to Group: "Property Info" and Category: "Total Units"
            - Map "Year Built", "Age", "Construction Year" to Group: "Property Info" and Category: "Year Built"
            - Map "Loan Balance", "Mortgage", "Existing Debt" to Group: "Debt" and Category: "Current Loan Balance"
            - Map general property stats (Roof Age, Sq Ft) to Group: "Property Info" and Category: "Property Characteristic"
            - Map Tax/Insurance to Group: "Tax & Insurance"
            - Map repairs/maintenance to Group: "Operating Expense"
            - For aggregated Excel documents, map to Category: "Property Characteristic" and Group: "Other"
            
            Use these exact group names:
            - Revenue
            - Operating Expense
            - Capital Expenditure
            - Property Info
            - Debt
            - Tax & Insurance
            - Other
            """
            
            response_text = await self.gemini_service.generate_content_async(prompt)
            
            # Clean and parse JSON
            cleaned_text = response_text.strip()
            if cleaned_text.startswith("```json"):
                cleaned_text = cleaned_text[7:]
            if cleaned_text.startswith("```"):
                cleaned_text = cleaned_text[3:]
            if cleaned_text.endswith("```"):
                cleaned_text = cleaned_text[:-3]
            cleaned_text = cleaned_text.strip()
            
            try:
                results = json.loads(cleaned_text)
            except json.JSONDecodeError:
                logger.error(f"Failed to parse batch normalization response: {cleaned_text[:100]}...")
                return [self._fallback_categorization(e.get("raw_text", "")) for e in expenses]
            
            # Create a map of id -> result for O(1) lookup
            result_map = {item.get("id"): item for item in results if isinstance(item, dict)}
            
            # Compile final list in order
            normalized_list = []
            for idx in range(len(expenses)):
                res = result_map.get(idx)
                if res:
                    normalized_list.append({
                        "normalized_value": res.get("category", "Other Operating Expenses"),
                        "category_group": res.get("group", "Other"),
                        "confidence": float(res.get("confidence", 0.5)),
                        "reasoning": res.get("reasoning", "")
                    })
                else:
                    # Fallback if item missing in response
                    normalized_list.append(self._fallback_categorization(expenses[idx].get("raw_text", "")))
                    
            return normalized_list

        except Exception as e:
            logger.error(f"Batch normalization failed: {str(e)}")
            # Fallback for all
            return [self._fallback_categorization(e.get("raw_text", "")) for e in expenses]

    async def normalize_expense_category(self, raw_text: str, item_type: str = "expense") -> Dict[str, Any]:
        """
        Use Gemini AI to map a raw description to a standard category and group.
        Kept for backward compatibility or single-item usage.
        """
        # Create a single item list and use batch processing
        batch_result = await self.normalize_expenses_batch([{"raw_text": raw_text, "type": item_type}])
        return batch_result[0] if batch_result else self._fallback_categorization(raw_text)
    
    def _fallback_categorization(self, expense_dict: Dict[str, Any]) -> Dict[str, Any]:
        """
        Simple keyword-based categorization fallback when Gemini is unavailable.
        """
        raw_text = expense_dict.get("raw_text", "") if isinstance(expense_dict, dict) else str(expense_dict)
        text_lower = raw_text.lower()
        item_type = expense_dict.get("type", "expense") if isinstance(expense_dict, dict) else "expense"
        subtype = expense_dict.get("subtype", "") if isinstance(expense_dict, dict) else ""
        
        # Handle receivables (Past Due)
        if item_type == "receivable" or any(keyword in text_lower for keyword in ["past due", "delinquent", "arrears"]):
            return {
                "normalized_value": "Accounts Receivable",
                "category_group": "Other",
                "confidence": 0.95,
                "reasoning": "Receivable/Past Due amount - not revenue"
            }
        
        # Handle revenue subtypes
        if item_type == "revenue":
            if subtype == "rent" or ("rent" in text_lower and "late" not in text_lower):
                return {
                    "normalized_value": "Gross Potential Rent",
                    "category_group": "Revenue",
                    "confidence": 0.9,
                    "reasoning": "Rental income"
                }
            elif subtype == "late_fee" or any(keyword in text_lower for keyword in ["late fee", "late charge", "penalty"]):
                return {
                    "normalized_value": "Other Income",
                    "category_group": "Revenue",
                    "confidence": 0.9,
                    "reasoning": "Late fee income"
                }
            elif subtype == "other_income" or any(keyword in text_lower for keyword in ["laundry", "parking", "pet fee"]):
                return {
                    "normalized_value": "Other Income",
                    "category_group": "Revenue",
                    "confidence": 0.9,
                    "reasoning": "Other income source"
                }
            elif subtype == "reimbursement" or "reimbursement" in text_lower:
                return {
                    "normalized_value": "Reimbursements",
                    "category_group": "Revenue",
                    "confidence": 0.9,
                    "reasoning": "Tenant reimbursement"
                }
        
        # Handle capital expenditures
        if item_type == "capex" or any(keyword in text_lower for keyword in ["electrical upgrade", "major renovation", "roof replacement"]):
            return {
                "normalized_value": "Capital Reserves",
                "category_group": "Capital Expenditure",
                "confidence": 0.85,
                "reasoning": "Capital expenditure"
            }
        
        # Special handling for Excel aggregated entries
        if "rent roll" in text_lower:
            return {
                "normalized_value": "Property Characteristic",
                "category_group": "Other",
                "confidence": 1.0,
                "reasoning": "Rent Roll document aggregation"
            }
        
        if "t12 statement" in text_lower or "financial statement" in text_lower or "p&l statement" in text_lower:
            return {
                "normalized_value": "Property Characteristic",
                "category_group": "Other",
                "confidence": 1.0,
                "reasoning": "Financial statement document aggregation"
            }
        
        # Keyword mapping for operating expenses
        category_keywords = {
            "Purchase Price": (["purchase price","price", "asking price", "sale price"], "Property Info"),
            "Price per Unit": (["price per unit", "cost per unit", "asking price/unit", "$/unit"], "Property Info"),
            "Total Units": (["units", "total units", "unit count", "number of units"], "Property Info"),
            "Year Built": (["year built", "construction year", "built in"], "Property Info"),
            "Current Loan Balance": (["loan balance", "existing loan", "mortgage balance", "principal balance"], "Debt"),
            "Utilities": (["utility", "utilities", "electric", "gas", "water", "sewer", "trash", "garbage", "pg&e", "pge"], "Operating Expense"),
            "Real Estate Taxes": (["tax", "property tax", "real estate tax"], "Tax & Insurance"),
            "Repairs & Maintenance": (["repair", "maintenance", "r&m", "plumbing", "hvac", "painting"], "Operating Expense"),
            "Management Fees": (["management", "property management", "mgmt"], "Operating Expense"),
            "Insurance": (["insurance", "liability", "property insurance"], "Tax & Insurance"),
            "Contract Services": (["landscape", "landscaping", "gardening", "lawn"], "Operating Expense"),
            "Payroll": (["payroll", "salary", "wages", "employee"], "Operating Expense"),
            "General & Administrative": (["legal", "accounting", "professional", "consultant", "administrative", "office", "supplies"], "Operating Expense"),
            "Advertising & Marketing": (["marketing", "advertising", "leasing"], "Operating Expense"),
            "Property Characteristic": (["roof age", "sq ft", "square feet"], "Property Info"),
        }
        
        for category, (keywords, group) in category_keywords.items():
            if any(keyword in text_lower for keyword in keywords):
                confidence = 0.85 if len([k for k in keywords if k in text_lower]) > 1 else 0.75
                return {
                    "normalized_value": category,
                    "category_group": group,
                    "confidence": confidence,
                    "reasoning": "Keyword-based matching"
                }
        
        return {
            "normalized_value": "Other Operating Expenses",
            "category_group": "Operating Expense",
            "confidence": 0.5,
            "reasoning": "No clear category match found"
        }
    
    async def process_financial_documents(
        self,
        documents: List[Dict[str, Any]],
        progress_service: Any = None,
        task_id: Optional[str] = None,
        progress_start: int = 20,
        progress_end: int = 80,
        initial_completed_files: List[str] = None
    ) -> (List[NormalizedDataItem], List[OMProformaTable], List[str]):
        """
        Process multiple financial documents and return normalized expense items and OM proforma data.
        
        Args:
            documents: List of dicts with 'content' (bytes), 'filename', 'document_category'
            progress_service: Optional service to update progress
            task_id: Optional task ID for progress updates
            progress_start: Starting percentage for progress updates (default: 20)
            progress_end: Ending percentage for progress updates (default: 80)
            initial_completed_files: Optional list of files already completed in previous steps
            
        Returns:
            A tuple containing:
            - List of NormalizedDataItem objects ready for user verification
            - List of OMProformaTable objects
            - List of completed filenames
        """
        all_expenses = []
        om_proforma_results = []
        errors = []
        
        logger.info(f"Starting to process {len(documents)} documents in parallel")
        
        # Semaphore to limit concurrent processing (optional, but good practice)
        sem = asyncio.Semaphore(10)  # Adjust concurrency limit as needed

        # Progress tracking variables
        completed_count = 0
        total_count = len(documents)
        active_files = set()
        completed_files = set(initial_completed_files or [])

        async def update_progress(filename: str, status: str, category: str):
            nonlocal completed_count
            
            if status == "started":
                active_files.add(filename)
            elif status in ["completed", "failed"]:
                if filename in active_files:
                    active_files.remove(filename)
                completed_count += 1
                completed_files.add(filename)
            
            if progress_service and task_id:
                # Calculate percentage: Map 0..total to progress_start..progress_end
                pct_range = progress_end - progress_start
                if total_count > 0:
                    current_pct = progress_start + int((completed_count / total_count) * pct_range)
                else:
                    current_pct = progress_start
                
                # Calculate cumulative stats
                initial_count = len(initial_completed_files or [])
                cumulative_index = initial_count + completed_count
                cumulative_total = initial_count + total_count

                # Determine message
                if status == "started":
                    msg = f"Processing {filename}..."
                else:
                    msg = f"Processed {cumulative_index}/{cumulative_total} documents"

                await progress_service.update_progress(
                    task_id,
                    current_pct,
                    msg,
                    details={
                        "current_file": filename, # Most recently changed file
                        "document_category": category,
                        "file_index": cumulative_index,
                        "total_files": cumulative_total,
                        "active_files": list(active_files),
                        "completed_files": list(completed_files),
                        "status": "processing"
                    }
                )

        async def process_single_document(idx, doc):
            async with sem:
                local_expenses = []
                local_om_results = []
                
                file_content = doc.get("content")
                filename = doc.get("filename", "unknown")
                file_type = doc.get("type", "").lower()
                document_id = doc.get("document_id")
                category = doc.get("document_category", "Uncategorized")

                logger.info(f"Processing document {idx+1}/{len(documents)}: {filename} (type: {file_type})")
                
                # Notify start
                await update_progress(filename, "started", category)

                try:
                    if not file_content:
                        logger.warning(f"No content for document: {filename}")
                        await update_progress(filename, "failed", category)
                        return [], []

                    # OM Extraction
                    if doc.get("document_category") == DocumentType.OFFERING_MEMORANDUM.value:
                        logger.info(f"Running OM Proforma extraction on: {filename}")
                        try:
                            proforma_tables = await self.extract_om_proforma_from_pdf(file_content, filename)
                            if proforma_tables:
                                local_om_results.extend(proforma_tables)
                                logger.info(f"Successfully extracted {len(proforma_tables)} proforma tables from {filename}")
                        except Exception as e:
                            logger.error(f"Error extracting OM Proforma from {filename}: {e}")

                    expenses = []
                    if file_type in ["xlsx", "xls", "excel"] or filename.endswith((".xlsx", ".xls")):
                        logger.info(f"Extracting from Excel file: {filename}")
                        expenses = await self.extract_from_excel(file_content, filename)
                        logger.info(f"Extracted {len(expenses)} expenses from Excel: {filename}")
                    
                    elif file_type == "csv" or filename.lower().endswith(".csv"):
                        logger.info(f"Extracting from CSV file: {filename}")
                        expenses = await self.extract_from_csv(file_content, filename)
                        logger.info(f"Extracted {len(expenses)} expenses from CSV: {filename}")

                    elif file_type == "visual" or file_type == "pdf" or filename.lower().endswith((".pdf", ".png", ".jpg", ".jpeg")):
                        logger.info(f"Extracting from visual file: {filename}")
                        
                        mime_type = "application/pdf"
                        if filename.lower().endswith(".png"):
                            mime_type = "image/png"
                        elif filename.lower().endswith((".jpg", ".jpeg")):
                            mime_type = "image/jpeg"
                            
                        expenses = await self.extract_from_visual_document(file_content, filename, mime_type=mime_type)
                        logger.info(f"Extracted {len(expenses)} expenses from {filename}")
                        
                        if document_id:
                            for exp in expenses:
                                exp["document_id"] = document_id

                        if not expenses:
                            logger.warning(f"Visual extraction returned no expenses for {filename}, creating placeholder")
                            expenses = [{
                                "raw_text": f"Document - {filename} (No expenses extracted)",
                                "amount": 0.0,
                                "source_document": filename,
                                "document_id": document_id
                            }]
                    else:
                        logger.warning(f"Unsupported file type for {filename}")
                        await update_progress(filename, "failed", category)
                        return [], []

                    local_expenses.extend(expenses)
                    await update_progress(filename, "completed", category)
                    return local_expenses, local_om_results

                except Exception as e:
                    error_msg = f"Error processing {filename}: {str(e)}"
                    logger.error(error_msg, exc_info=True)
                    errors.append(error_msg)
                    
                    placeholder_expense = {
                        "raw_text": f"Document - {filename} (Processing failed: {str(e)[:100]})",
                        "amount": 0.0,
                        "source_document": filename,
                        "error": str(e)
                    }
                    await update_progress(filename, "failed", category)
                    return [placeholder_expense], local_om_results

        # Execute all document processing in parallel
        tasks = [process_single_document(idx, doc) for idx, doc in enumerate(documents)]
        
        # Use gather to wait for all
        results = await asyncio.gather(*tasks)
        
        # Flatten results
        for doc_expenses, doc_om_results in results:
            all_expenses.extend(doc_expenses)
            om_proforma_results.extend(doc_om_results)

        # Update progress after all files are processed
        if progress_service and task_id:
            await progress_service.update_progress(
                task_id,
                progress_end,
                f"Completed processing {len(documents)} files",
                details={
                    "file_index": len(documents),
                    "total_files": len(documents),
                    "active_files": [],
                    "completed_files": list(completed_files),
                    "status": "complete"
                }
            )
        
        logger.info(f"Total expenses extracted from all documents: {len(all_expenses)}")
        
        if errors:
            logger.warning(f"Encountered {len(errors)} errors during processing: {errors}")
        
        if not all_expenses:
            logger.warning("No expenses were extracted from any document")
            # Return empty list instead of raising exception, allowing process to continue with defaults
            if errors:
                logger.error(f"Extraction failed with errors: {'; '.join(errors)}")
            return [], om_proforma_results, list(completed_files)
        
        # Validate and fix expenses (filtering out totals, tuition, etc.) BEFORE batching
        # to ensure batch sizes align with normalization results.
        # This prevents misalignment in the zip() operation downstream.
        all_expenses = self._validate_and_fix_extraction(all_expenses)
        logger.info(f"Total expenses after validation/filtering: {len(all_expenses)}")

        # Normalize expenses using batch processing
        normalized_items: List[NormalizedDataItem] = []
        logger.info(f"Starting batch normalization of {len(all_expenses)} expenses...")
        
        # Process in chunks of 50 to avoid hitting token limits
        batch_size = 50
        
        # Create batches
        batches = [all_expenses[i:i + batch_size] for i in range(0, len(all_expenses), batch_size)]
        
        async def process_normalization_batch(batch_idx, chunk):
            local_items = []
            try:
                logger.info(f"Normalizing batch {batch_idx + 1}/{len(batches)} ({len(chunk)} items)")
                batch_normalizations = await self.normalize_expenses_batch(chunk)
                
                for idx, (expense, normalization) in enumerate(zip(chunk, batch_normalizations)):
                    try:
                        raw_text = expense.get("raw_text", "")
                        amount = expense.get("amount")
                        item_type = expense.get("type", "expense")
                        
                        category_group = normalization.get("category_group", "Other")
                        field_type = "expense_category"
                        if category_group == "Property Info":
                            field_type = "property_meta"
                        elif category_group == "Revenue":
                            field_type = "revenue_item"
                        
                        try:
                            group_enum = CategoryGroup(category_group)
                        except ValueError:
                            try:
                                if "Expense" in category_group:
                                    group_enum = CategoryGroup.OPERATING_EXPENSE
                                elif "Revenue" in category_group or "Income" in category_group:
                                    group_enum = CategoryGroup.REVENUE
                                elif "Property" in category_group:
                                    group_enum = CategoryGroup.PROPERTY_INFO
                                elif "Debt" in category_group:
                                    group_enum = CategoryGroup.DEBT
                                else:
                                    group_enum = CategoryGroup.OTHER
                            except:
                                group_enum = CategoryGroup.OTHER
                        
                        # Extract year
                        expense_year = expense.get("expense_year")
                        
                        meta = {
                            "amount": amount,
                            "reasoning": normalization.get("reasoning", ""),
                            "row_count": expense.get("row_count"),
                            "categories_found": expense.get("categories_found"),
                            "original_type": item_type,
                            "expense_year": expense_year,
                            "page_number": expense.get("page_number"),
                            "bbox": expense.get("bbox"),
                            "document_id": expense.get("document_id")
                        }

                        # Create a temp ID, we will re-index later if needed to be perfectly sequential
                        # or just use UUIDs. Here using a placeholder index that might collide if not careful
                        # but we are appending to a local list.
                        item = NormalizedDataItem(
                            id=f"item_placeholder",
                            raw_text=raw_text,
                            normalized_value=normalization.get("normalized_value", "Other Operating Expenses"),
                            field_type=field_type,
                            category_group=group_enum,
                            data_classification=DataClassification.SOURCED,
                            confidence=normalization.get("confidence", 0.5),
                            user_verified=False,
                            source_document=expense.get("source_document", "Unknown"),
                            metadata=meta
                        )
                        local_items.append(item)
                        
                        if self.batch_logging_service:
                             self.batch_logging_service.log_normalization(
                                 document_id=expense.get("document_id", "unknown"),
                                 filename=expense.get("source_document", "unknown"),
                                 raw_text=raw_text,
                                 amount=float(amount or 0.0),
                                 normalized_value=normalization.get("normalized_value", ""),
                                 category_group=normalization.get("category_group", ""),
                                 confidence=normalization.get("confidence", 0.0),
                                 source_document=expense.get("source_document", "unknown")
                             )

                    except Exception as item_error:
                        logger.error(f"Error creating normalized item: {str(item_error)}")
                        if self.batch_logging_service:
                            self.batch_logging_service.log_error("batch", "create_normalized_item", str(item_error))
                        continue
                return local_items
            except Exception as batch_error:
                logger.error(f"Error processing batch {batch_idx}: {str(batch_error)}")
                if self.batch_logging_service:
                    self.batch_logging_service.log_error("batch", "process_normalization_batch", str(batch_error))
                return []

        # Run normalization batches in parallel
        norm_results = await asyncio.gather(*[process_normalization_batch(i, batch) for i, batch in enumerate(batches)])
        
        # Flatten results
        for batch_items in norm_results:
            normalized_items.extend(batch_items)
            
        # Re-assign sequential IDs
        for idx, item in enumerate(normalized_items):
            item.id = f"item_{idx}"
        
        logger.info(f"Normalization complete: {len(normalized_items)} items ready for verification")
        logger.info(f"Processed {len(documents)} documents, extracted {len(normalized_items)} normalized items and {len(om_proforma_results)} OM proforma tables.")
        return normalized_items, om_proforma_results, list(completed_files)
