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
from app.models.schemas import NormalizedDataItem, DocumentType

logger = logging.getLogger(__name__)


class MultiDocumentExtractionService:
    """Service for extracting and normalizing financial data from multiple document types."""
    
    # Standard expense categories for normalization
    STANDARD_CATEGORIES = [
        "Utilities",
        "Real Estate Taxes",
        "Repairs & Maintenance",
        "Management Fees",
        "Insurance",
        "Landscaping",
        "Payroll",
        "Professional Fees",
        "Marketing",
        "Administrative",
        "Other Operating Expenses"
    ]
    
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
            logger.error(f"Error extracting from Excel file {filename}: {str(e)}", exc_info=True)
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
                Analyze this financial document (T12, P&L, Income Statement, Tax Bill, or Utility Bill) and extract ALL expense line items.
                
                For each expense, provide:
                1. The exact text/description as it appears in the document
                2. The amount (annual or monthly - specify which)
                
                Return the data as a JSON array with this structure:
                [
                    {
                        "raw_text": "Exact expense description",
                        "amount": 12345.67,
                        "period": "annual" or "monthly"
                    }
                ]
                
                Only include operating expenses. Skip revenue, income, NOI, and total/subtotal rows.
                If no expenses are found, return an empty array [].
                
                IMPORTANT: Return ONLY the JSON array, no additional text or explanation.
                """
                
                response = self.gemini_service.model.generate_content([uploaded_file, prompt])
                
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
                    # Convert monthly to annual if needed
                    if expense.get("period") == "monthly":
                        expense["amount"] = expense["amount"] * 12
                
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
    
    async def normalize_expense_category(self, raw_text: str) -> Dict[str, Any]:
        """
        Use Gemini AI to map a raw expense description to a standard category.
        
        Args:
            raw_text: Raw expense description from the document
            
        Returns:
            Dictionary with normalized_value and confidence score
        """
        if not self.gemini_service:
            # Fallback to simple keyword matching
            return self._fallback_categorization(raw_text)
        
        try:
            prompt = f"""
            You are a commercial real estate financial analyst. Map this expense description to the most appropriate standard category.
            
            Expense Description: "{raw_text}"
            
            Standard Categories:
            {chr(10).join(f"- {cat}" for cat in self.STANDARD_CATEGORIES)}
            
            Respond with ONLY a JSON object in this exact format:
            {{
                "category": "Exact category name from the list above",
                "confidence": 0.95,
                "reasoning": "Brief explanation"
            }}
            
            Rules:
            - Choose the MOST specific and appropriate category
            - Confidence should be 0.0 to 1.0 (0.95+ for obvious matches, 0.7-0.94 for reasonable matches, below 0.7 for uncertain)
            - If uncertain, choose the closest match but lower the confidence
            """
            
            response = self.gemini_service.generate_content(prompt)
            response_text = response.strip()
            
            # Remove markdown code blocks if present
            if response_text.startswith("```json"):
                response_text = response_text[7:]
            if response_text.startswith("```"):
                response_text = response_text[3:]
            if response_text.endswith("```"):
                response_text = response_text[:-3]
            
            result = json.loads(response_text.strip())
            
            return {
                "normalized_value": result.get("category", "Other Operating Expenses"),
                "confidence": float(result.get("confidence", 0.5)),
                "reasoning": result.get("reasoning", "")
            }
            
        except Exception as e:
            logger.error(f"Error normalizing category for '{raw_text}': {str(e)}")
            return self._fallback_categorization(raw_text)
    
    def _fallback_categorization(self, raw_text: str) -> Dict[str, Any]:
        """
        Simple keyword-based categorization fallback when Gemini is unavailable.
        """
        text_lower = raw_text.lower()
        
        # Keyword mapping
        category_keywords = {
            "Utilities": ["utility", "utilities", "electric", "gas", "water", "sewer", "trash", "garbage", "pg&e", "pge"],
            "Real Estate Taxes": ["tax", "property tax", "real estate tax"],
            "Repairs & Maintenance": ["repair", "maintenance", "r&m", "plumbing", "hvac", "painting"],
            "Management Fees": ["management", "property management", "mgmt"],
            "Insurance": ["insurance", "liability", "property insurance"],
            "Landscaping": ["landscape", "landscaping", "gardening", "lawn"],
            "Payroll": ["payroll", "salary", "wages", "employee"],
            "Professional Fees": ["legal", "accounting", "professional", "consultant"],
            "Marketing": ["marketing", "advertising", "leasing"],
            "Administrative": ["administrative", "office", "supplies", "postage"],
        }
        
        for category, keywords in category_keywords.items():
            if any(keyword in text_lower for keyword in keywords):
                confidence = 0.85 if len([k for k in keywords if k in text_lower]) > 1 else 0.75
                return {
                    "normalized_value": category,
                    "confidence": confidence,
                    "reasoning": "Keyword-based matching"
                }
        
        return {
            "normalized_value": "Other Operating Expenses",
            "confidence": 0.5,
            "reasoning": "No clear category match found"
        }
    
    async def process_financial_documents(
        self,
        documents: List[Dict[str, Any]]
    ) -> List[NormalizedDataItem]:
        """
        Process multiple financial documents and return normalized expense items.
        
        Args:
            documents: List of dicts with 'content' (bytes), 'filename', and 'type' (pdf/excel)
            
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
            if errors:
                # If we had errors, raise them so the user knows what went wrong
                raise Exception(f"Failed to extract expenses. Errors: {'; '.join(errors)}")
            return []
        
        # Normalize each expense using batch processing for better performance
        normalized_items = []
        logger.info(f"Starting normalization of {len(all_expenses)} expenses...")
        
        # Use fallback categorization for better performance with large datasets
        # For production, consider implementing batch Gemini API calls
        for idx, expense in enumerate(all_expenses):
            try:
                # Use fallback categorization which is much faster
                # This avoids making 100+ sequential API calls to Gemini
                normalization = self._fallback_categorization(expense["raw_text"])
                
                item = NormalizedDataItem(
                    id=f"exp_{len(normalized_items)}",
                    raw_text=expense["raw_text"],
                    normalized_value=normalization["normalized_value"],
                    field_type="expense_category",
                    confidence=normalization["confidence"],
                    user_verified=False,
                    source_document=expense["source_document"],
                    metadata={
                        "amount": expense.get("amount"),
                        "reasoning": normalization.get("reasoning", "")
                    }
                )
                normalized_items.append(item)
                
                # Log progress every 20 items
                if (idx + 1) % 20 == 0:
                    logger.info(f"Normalized {idx + 1}/{len(all_expenses)} expenses...")
                    
            except Exception as e:
                logger.error(f"Error normalizing expense '{expense.get('raw_text')}': {str(e)}")
                # Continue with other items
        
        logger.info(f"Normalization complete: {len(normalized_items)} items ready for verification")
        logger.info(f"Processed {len(documents)} documents, extracted {len(normalized_items)} normalized items")
        return normalized_items
