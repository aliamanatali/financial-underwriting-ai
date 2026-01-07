"""
Multi-Document Extraction Service
Handles extraction of financial data from PDFs and Excel files in deal packages.
"""

import io
import logging
import json
from typing import List, Dict, Any, Optional
import openpyxl
from openpyxl.worksheet.worksheet import Worksheet
import google.generativeai as genai
from app.models.schemas import NormalizedDataItem, DocumentType, CategoryGroup, DataClassification, ExpenseCategory

logger = logging.getLogger(__name__)


class MultiDocumentExtractionService:
    """Service for extracting and normalizing financial data from multiple document types."""
    
    # Standard expense categories for normalization
    STANDARD_CATEGORIES = [e.value for e in ExpenseCategory]
    
    def __init__(self, gemini_service=None):
        """Initialize the extraction service with optional Gemini service."""
        self.gemini_service = gemini_service
    
    async def extract_from_excel(self, file_content: bytes, filename: str) -> List[Dict[str, Any]]:
        """
        Extract aggregated financial data from Excel files (T12, P&L, Rent Roll, etc.).
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
            raise

    def _extract_from_excel_sync(self, file_content: bytes, filename: str) -> List[Dict[str, Any]]:
        """Synchronous implementation of Excel extraction for thread pool execution."""
        try:
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
            total_amount = 0.0
            row_count = 0
            categories = set()
            
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
            aggregated_entry = {
                "raw_text": f"{doc_type} - {filename}",
                "amount": total_amount,
                "source_document": filename,
                "row_count": row_count,
                "categories_found": list(categories)[:5]  # Keep first 5 categories as sample
            }
            
            logger.info(f"Extracted aggregated data from {filename}: {row_count} rows, total amount: ${total_amount:,.2f}")
            
            return [aggregated_entry]  # Return single entry instead of multiple
            
        except Exception as e:
            logger.error(f"Error inside sync Excel extraction for {filename}: {str(e)}", exc_info=True)
            raise
    
    async def extract_from_pdf(self, file_content: bytes, filename: str) -> List[Dict[str, Any]]:
        """
        Extract expense line items from PDF files using Gemini Vision API.
        
        Args:
            file_content: Raw bytes of the PDF file
            filename: Name of the file for reference
            
        Returns:
            List of dictionaries containing raw expense data
        """
        if not self.gemini_service:
            logger.warning("Gemini service not available for PDF extraction")
            return []
        
        try:
            logger.info(f"Starting PDF extraction for {filename} ({len(file_content)} bytes)")
            
            # Upload PDF to Gemini using the File API
            import base64
            import tempfile
            
            # For PDFs, we need to use the File API
            # Create a temporary file
            with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as tmp_file:
                tmp_file.write(file_content)
                tmp_path = tmp_file.name
            
            try:
                # Upload the file to Gemini
                uploaded_file = genai.upload_file(tmp_path, mime_type="application/pdf")
                logger.info(f"Uploaded PDF to Gemini: {uploaded_file.name}")
                
                prompt = """
                Analyze this financial document (T12, P&L, Income Statement, Tax Bill, Utility Bill, Lease Agreement, Offering Memorandum, or Disclosure) and extract ALL financial items.
                
                You must distinguish between:
                1. Revenue / Income (e.g., Rent, Reimbursements, Other Income)
                2. Operating Expenses (e.g., Taxes, Insurance, R&M, Management, Utilities)
                3. Property Characteristics (e.g., "Year Built", "Roof Age", "Unit Count", "Rentable Sq Ft")
                4. Capital Expenditures (e.g., "New Roof", "HVAC Replacement")
                
                For each item, provide:
                1. The exact text/description as it appears in the document
                2. The amount (annual or monthly) if applicable.
                3. The item type: "revenue", "expense", "property_info", "capex".
                
                Return the data as a JSON array with this structure:
                [
                    {
                        "raw_text": "Exact description",
                        "amount": 12345.67, // or null
                        "period": "annual" or "monthly" or "one-time",
                        "type": "revenue" // or "expense", "property_info", "capex"
                    }
                ]
                
                IMPORTANT:
                - Do NOT categorize Revenue items (like "Rental Income", "Lease Payments") as Expenses.
                - Do NOT categorize Property Characteristics (like "Year Built") as Expenses.
                - If the document is a Rent Roll or Lease, capture the Rental Income.
                
                Return ONLY the JSON array, no additional text or explanation.
                """
                
                response = await self.gemini_service.model.generate_content_async([uploaded_file, prompt])
                
                # Parse JSON response
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
                
                logger.info(f"Extracted {len(expenses_data)} expense items from PDF {filename}")
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
                "raw_text": f"PDF Document - {filename} (JSON parsing error)",
                "amount": 0.0,
                "source_document": filename,
                "error": str(e)
            }]
        except Exception as e:
            logger.error(f"Error extracting from PDF file {filename}: {str(e)}", exc_info=True)
            # Return placeholder instead of raising
            return [{
                "raw_text": f"PDF Document - {filename} (Extraction error: {str(e)[:100]})",
                "amount": 0.0,
                "source_document": filename,
                "error": str(e)
            }]
    
    async def normalize_expenses_batch(self, expenses: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Batch normalize expenses using Gemini to reduce API calls and latency.
        """
        if not expenses:
            return []
            
        if not self.gemini_service:
            return [self._fallback_categorization(e.get("raw_text", "")) for e in expenses]

        try:
            # Prepare items for prompt
            items_payload = []
            for idx, exp in enumerate(expenses):
                items_payload.append({
                    "id": idx,
                    "text": exp.get("raw_text", ""),
                    "type": exp.get("type", "expense")
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
                    "category": "Exact category name from the list above, or 'Uncategorized'",
                    "group": "Revenue" | "Operating Expense" | "Capital Expenditure" | "Property Info" | "Debt" | "Tax & Insurance" | "Other",
                    "confidence": 0.95,
                    "reasoning": "Brief explanation"
                }}
            ]
            
            Rules:
            - Map income/rent to Group: "Revenue".
            - Map property stats (Year Built, Roof Age) to Group: "Property Info" and Category: "Property Characteristic".
            - Map Tax/Insurance to Group: "Tax & Insurance".
            - Map repairs/maintenance to Group: "Operating Expense".
            
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
    
    def _fallback_categorization(self, raw_text: str) -> Dict[str, Any]:
        """
        Simple keyword-based categorization fallback when Gemini is unavailable.
        """
        text_lower = raw_text.lower()
        
        # Keyword mapping
        category_keywords = {
            "Utilities": (["utility", "utilities", "electric", "gas", "water", "sewer", "trash", "garbage", "pg&e", "pge"], "Operating Expense"),
            "Real Estate Taxes": (["tax", "property tax", "real estate tax"], "Tax & Insurance"),
            "Repairs & Maintenance": (["repair", "maintenance", "r&m", "plumbing", "hvac", "painting"], "Operating Expense"),
            "Management Fees": (["management", "property management", "mgmt"], "Operating Expense"),
            "Insurance": (["insurance", "liability", "property insurance"], "Tax & Insurance"),
            "Landscaping": (["landscape", "landscaping", "gardening", "lawn"], "Operating Expense"),
            "Payroll": (["payroll", "salary", "wages", "employee"], "Operating Expense"),
            "Professional Fees": (["legal", "accounting", "professional", "consultant"], "Operating Expense"),
            "Marketing": (["marketing", "advertising", "leasing"], "Operating Expense"),
            "Administrative": (["administrative", "office", "supplies", "postage"], "Operating Expense"),
            "Gross Potential Rent": (["rent", "income", "revenue", "lease payment"], "Revenue"),
            "Property Characteristic": (["year built", "roof age", "units", "sq ft"], "Property Info"),
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
        progress_end: int = 80
    ) -> List[NormalizedDataItem]:
        """
        Process multiple financial documents and return normalized expense items.
        
        Args:
            documents: List of dicts with 'content' (bytes), 'filename', and 'type' (pdf/excel)
            progress_service: Optional service to update progress
            task_id: Optional task ID for progress updates
            progress_start: Starting percentage for progress updates (default: 20)
            progress_end: Ending percentage for progress updates (default: 80)
            
        Returns:
            List of NormalizedDataItem objects ready for user verification
        """
        all_expenses = []
        errors = []
        
        logger.info(f"Starting to process {len(documents)} documents")
        
        # Extract from each document
        for idx, doc in enumerate(documents):
            file_content = doc.get("content")
            filename = doc.get("filename", "unknown")
            file_type = doc.get("type", "").lower()
            
            if progress_service and task_id:
                # Calculate progress based on provided range
                start_pct = progress_start
                end_pct = progress_end
                # If we have documents, calculate step. If 0 documents, logic won't run loop anyway.
                pct_per_doc = (end_pct - start_pct) / max(len(documents), 1)
                current_pct = int(start_pct + (idx * pct_per_doc))
                
                await progress_service.update_progress(
                    task_id,
                    current_pct,
                    f"Processing file: {filename}",
                    details={
                        "current_file": filename,
                        "file_index": idx + 1,
                        "total_files": len(documents),
                        "file_type": file_type
                    }
                )
            
            logger.info(f"Processing document {idx+1}/{len(documents)}: {filename} (type: {file_type})")
            
            if not file_content:
                logger.warning(f"No content for document: {filename}")
                continue
            
            try:
                if file_type in ["xlsx", "xls", "excel"] or filename.endswith((".xlsx", ".xls")):
                    logger.info(f"Extracting from Excel file: {filename}")
                    expenses = await self.extract_from_excel(file_content, filename)
                    logger.info(f"Extracted {len(expenses)} expenses from Excel: {filename}")
                elif file_type == "pdf" or filename.endswith(".pdf"):
                    logger.info(f"Extracting from PDF file: {filename}")
                    expenses = await self.extract_from_pdf(file_content, filename)
                    logger.info(f"Extracted {len(expenses)} expenses from PDF: {filename}")
                    
                    # If PDF extraction returned empty, create a placeholder entry
                    if not expenses:
                        logger.warning(f"PDF extraction returned no expenses for {filename}, creating placeholder")
                        expenses = [{
                            "raw_text": f"PDF Document - {filename} (No expenses extracted)",
                            "amount": 0.0,
                            "source_document": filename
                        }]
                else:
                    logger.warning(f"Unsupported file type for {filename}")
                    continue
                
                all_expenses.extend(expenses)
                
            except Exception as e:
                error_msg = f"Error processing {filename}: {str(e)}"
                logger.error(error_msg, exc_info=True)
                errors.append(error_msg)
                
                # Add a placeholder entry for failed documents so they still appear
                placeholder_expense = {
                    "raw_text": f"Document - {filename} (Processing failed: {str(e)[:100]})",
                    "amount": 0.0,
                    "source_document": filename,
                    "error": str(e)
                }
                all_expenses.append(placeholder_expense)
                logger.info(f"Added placeholder entry for failed document: {filename}")
                # Continue processing other documents
        
        logger.info(f"Total expenses extracted from all documents: {len(all_expenses)}")
        
        if errors:
            logger.warning(f"Encountered {len(errors)} errors during processing: {errors}")
        
        if not all_expenses:
            logger.warning("No expenses were extracted from any document")
            # Return empty list instead of raising exception, allowing process to continue with defaults
            if errors:
                logger.error(f"Extraction failed with errors: {'; '.join(errors)}")
            return []
        
        # Normalize expenses using batch processing
        normalized_items: List[NormalizedDataItem] = []
        logger.info(f"Starting batch normalization of {len(all_expenses)} expenses...")
        
        # Process in chunks of 50 to avoid hitting token limits
        batch_size = 50
        
        for i in range(0, len(all_expenses), batch_size):
            chunk = all_expenses[i:i + batch_size]
            logger.info(f"Normalizing batch {i//batch_size + 1}/{(len(all_expenses) + batch_size - 1)//batch_size + 1} ({len(chunk)} items)")
            
            try:
                # Get normalized data for the entire chunk
                batch_normalizations = await self.normalize_expenses_batch(chunk)
                
                for idx, (expense, normalization) in enumerate(zip(chunk, batch_normalizations)):
                    try:
                        raw_text = expense.get("raw_text", "")
                        amount = expense.get("amount")
                        item_type = expense.get("type", "expense")
                        
                        # Determine field type based on the group returned
                        category_group = normalization.get("category_group", "Other")
                        field_type = "expense_category"
                        if category_group == "Property Info":
                            field_type = "property_meta"
                        elif category_group == "Revenue":
                            field_type = "revenue_item"
                        
                        # Map string group to Enum if possible, otherwise default to OTHER
                        try:
                            group_enum = CategoryGroup(category_group)
                        except ValueError:
                            # Try to handle common variations
                            try:
                                if "Expense" in category_group:
                                    group_enum = CategoryGroup.OPERATING_EXPENSE
                                elif "Revenue" in category_group or "Income" in category_group:
                                    group_enum = CategoryGroup.REVENUE
                                else:
                                    group_enum = CategoryGroup.OTHER
                            except:
                                group_enum = CategoryGroup.OTHER
                            
                        item = NormalizedDataItem(
                            id=f"item_{len(normalized_items)}",
                            raw_text=raw_text,
                            normalized_value=normalization.get("normalized_value", "Other Operating Expenses"),
                            field_type=field_type,
                            category_group=group_enum,
                            data_classification=DataClassification.SOURCED,
                            confidence=normalization.get("confidence", 0.5),
                            user_verified=False,
                            source_document=expense.get("source_document", "Unknown"),
                            metadata={
                                "amount": amount,
                                "reasoning": normalization.get("reasoning", ""),
                                "row_count": expense.get("row_count"),
                                "categories_found": expense.get("categories_found"),
                                "original_type": item_type
                            }
                        )
                        normalized_items.append(item)
                        
                    except Exception as item_error:
                        logger.error(f"Error creating normalized item: {str(item_error)}")
                        continue
                        
            except Exception as batch_error:
                logger.error(f"Error processing batch starting at {i}: {str(batch_error)}")
                # Continue to next batch
        
        logger.info(f"Normalization complete: {len(normalized_items)} items ready for verification")
        logger.info(f"Processed {len(documents)} documents, extracted {len(normalized_items)} normalized items")
        return normalized_items
