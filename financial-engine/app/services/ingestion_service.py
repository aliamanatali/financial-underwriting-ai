import json
import pandas as pd
from typing import List, Dict, Any, Optional
from fastapi import HTTPException
from app.models.schemas import RentRollItem, PropertyMeta, UnderwritingAnalysis, StandardizedExpense, ExpenseCategory, AuditLog, RentRollSummary
from app.services.normalization_service import NormalizationService
from app.services.gemini_client import GeminiClient
from app.services.ocr_backend_client import OcrBackendClient
from app.services.extract_om_details import OMScraperService

class IngestionService:
    def __init__(self):
        self.gemini_client = GeminiClient()
        self.normalization_service = NormalizationService(llm_service=self.gemini_client)
        self.ocr_backend_client = OcrBackendClient()
        self.om_scraper_service = OMScraperService(gemini_client=self.gemini_client)

    def _get_val(self, row, keys, default=None):
        """Helper to get value from row using multiple possible keys (case-insensitive)."""
        # Convert row keys to lower for lookup
        row_keys_lower = {str(k).lower().strip(): k for k in row.keys()}
        
        for key in keys:
            key_lower = key.lower().strip()
            if key_lower in row_keys_lower:
                actual_key = row_keys_lower[key_lower]
                val = row.get(actual_key)
                if val is not None and str(val).strip() != "":
                    return val
        return default

    def _parse_float(self, val):
        """Safely parse float from string, handling currency symbols and other junk."""
        if val is None:
            return 0.0
        if isinstance(val, (int, float)):
            return float(val)
        
        s = str(val).strip()
        if not s or s == "-":
            return 0.0
            
        # Remove currency symbols and commas
        s = s.replace("$", "").replace(",", "").replace(" ", "")
        
        # Handle parentheses for negative numbers (e.g. "(500)" -> "-500")
        if s.startswith("(") and s.endswith(")"):
            s = "-" + s[1:-1]
            
        try:
            return float(s)
        except (ValueError, TypeError):
            return 0.0

    def _parse_int(self, val):
        """Safely parse int from string."""
        if val is None:
            return 0
        if isinstance(val, int):
            return val
        if isinstance(val, float):
            return int(val)
            
        s = str(val).strip()
        if not s or s == "-":
            return 0
            
        # Remove commas and non-numeric chars except digits
        # Keep it simple: try float first then int
        try:
            return int(self._parse_float(val))
        except (ValueError, TypeError):
            return 0

    def ingest_rent_roll_from_excel(self, file_path: str, property_meta: PropertyMeta) -> List[RentRollItem]:
        import os
        filename = os.path.basename(file_path)
        
        # Support Multi-Sheet Extraction
        try:
            xls = pd.ExcelFile(file_path)
        except Exception as e:
            raise ValueError(f"Failed to read Excel file: {e}")

        best_rent_roll = []
        best_sheet_name = ""
        
        # Iterate through all sheets to find the best candidate
        for sheet_name in xls.sheet_names:
            try:
                df = pd.read_excel(xls, sheet_name=sheet_name, header=None)
                if df.empty:
                    continue
                    
                # logic to find the row that contains "Unit" AND ("Rent" OR "Month" OR "Amount")
                header_row_idx = None
                for i, row in df.iterrows():
                    # Limit to first 30 rows for header search to improve performance
                    if i > 30:
                        break
                        
                    # Clean string conversion handling NaNs
                    row_str = []
                    for x in row.tolist():
                        s = str(x).lower().strip()
                        if s in ['nan', 'none', '', 'nat']:
                            s = ""
                        row_str.append(s)

                    # Check for Unit identifier (Unit, Apt, Suite, #)
                    unit_indices = [idx for idx, x in enumerate(row_str) if any(k in x for k in ["unit", "apt", "apartment", "suite", "#"]) and len(x) < 30]
                    
                    # Check for Rent identifier (Rent, $/Month, Amount, Rate)
                    rent_indices = [idx for idx, x in enumerate(row_str) if any(k in x for k in ["rent", "month", "amount", "rate", "price", "charge"]) and len(x) < 30]
                    
                    # Check for Tenant identifier (Tenant, Resident, Name)
                    tenant_indices = [idx for idx, x in enumerate(row_str) if any(k in x for k in ["tenant", "resident", "name", "lessee"]) and len(x) < 30]

                    has_unit = len(unit_indices) > 0
                    has_rent = len(rent_indices) > 0
                    has_tenant = len(tenant_indices) > 0
                    
                    if has_unit and (has_rent or has_tenant):
                        # Robustness Check: Ensure we have matches in DISTINCT columns to avoid Title rows
                        all_match_indices = set(unit_indices + rent_indices + tenant_indices)
                        
                        # If we have matches in at least 2 distinct columns, it's likely a real header.
                        if len(all_match_indices) >= 2:
                            header_row_idx = i
                            break

                if header_row_idx is None:
                    continue

                # Reload with correct header
                df_data = pd.read_excel(xls, sheet_name=sheet_name, header=header_row_idx)
                df_data = df_data.fillna("")

                current_sheet_roll = []
                for _, row in df_data.iterrows():
                    # Use case-insensitive lookup
                    unit_number = str(self._get_val(row, ["Unit Number", "Unit #", "Unit", "Apt No"], ""))
                    tenant_name = str(self._get_val(row, ["Tenant Name", "Tenant", "Resident", "Tenant(s)", "Name"], ""))
                    
                    # Skip empty rows or summary rows
                    if not unit_number and not tenant_name:
                        continue
                    if str(unit_number).lower() in ["total", "totals", "average", "averages", "nan", ""]:
                        continue
                        
                    # Skip rows where unit number is too long (likely a note)
                    if len(unit_number) > 20:
                        continue

                    current_sheet_roll.append(RentRollItem(
                            unit_number=unit_number,
                            unit_type=str(self._get_val(row, ["Unit Type", "Type", "Floor Plan", "Occupancy Type"], "")),
                            unit_size=self._parse_int(self._get_val(row, ["Unit Size", "Sq Ft", "Square Feet", "SF", "Size", "Area"], 0)),
                            tenant_name=tenant_name,
                            current_rent=self._parse_float(self._get_val(row, ["Rent Amount", "Current Rent", "Rent", "Total Rent", "$/Month", "Rate", "2024 Rent"], 0.0)),
                            stabilized_rent=self._parse_float(self._get_val(row, ["Stabilized Rent", "Stabilized"], 0.0)),
                            market_rent=self._parse_float(self._get_val(row, ["Market Rent", "Market", "Pro Forma"], 0.0)),
                            move_in_date=str(self._get_val(row, ["Move In Date", "Move-In Date", "Move In"], "")),
                            lease_start=str(self._get_val(row, ["Lease Start", "Lease Start Date", "Start", "Start Date"], "")),
                            lease_end=str(self._get_val(row, ["Lease End", "Lease End Date", "End", "End Date", "Lease Exp"], "")),
                            deposit=self._parse_float(self._get_val(row, ["Deposit", "Security Deposit", "Sec Dep"], 0.0)),
                            parking=str(self._get_val(row, ["Parking", "Parking Space", "Parking Space #"], "")),
                            comments=str(self._get_val(row, ["Comments", "Comment", "Coment", "Notes"], "")),
                            source_file=f"{filename} | Sheet: {sheet_name}",
                            floor=str(self._get_val(row, ["Floor", "Level"], ""))
                    ))
                
                # Heuristic: The sheet with the most valid unit rows is likely the Rent Roll
                if len(current_sheet_roll) > len(best_rent_roll):
                    best_rent_roll = current_sheet_roll
                    best_sheet_name = sheet_name
                    
            except Exception as e:
                # Log but continue to next sheet
                print(f"Error processing sheet {sheet_name}: {e}")
                continue

        if not best_rent_roll:
            raise ValueError("Could not find valid Rent Roll data in any sheet of the Excel file")

        return best_rent_roll
        for _, row in df.iterrows():
            # Use case-insensitive lookup
            unit_number = str(self._get_val(row, ["Unit Number", "Unit #", "Unit"], ""))
            tenant_name = str(self._get_val(row, ["Tenant Name", "Tenant", "Resident"], ""))
            
            if not unit_number and not tenant_name:
                continue
                
            # Skip summary rows
            if str(unit_number).lower() in ["total", "totals", "average", "averages"]:
                continue

            rent_roll.append(RentRollItem(
                    unit_number=unit_number,
                    unit_type=str(self._get_val(row, ["Unit Type", "Type", "Floor Plan", "Occupancy Type"], "")),
                    unit_size=self._parse_int(self._get_val(row, ["Unit Size", "Sq Ft", "Square Feet", "SF", "Size", "Area"], 0)),
                    tenant_name=tenant_name,
                    current_rent=self._parse_float(self._get_val(row, ["Rent Amount", "Current Rent", "Rent", "Total Rent", "$/Month", "Rate"], 0.0)),
                    stabilized_rent=self._parse_float(self._get_val(row, ["Stabilized Rent", "Stabilized"], 0.0)),
                    market_rent=self._parse_float(self._get_val(row, ["Market Rent", "Market", "Pro Forma"], 0.0)),
                    move_in_date=str(self._get_val(row, ["Move In Date", "Move-In Date", "Move In"], "")),
                    lease_start=str(self._get_val(row, ["Lease Start", "Lease Start Date", "Start", "Start Date"], "")),
                    lease_end=str(self._get_val(row, ["Lease End", "Lease End Date", "End", "End Date"], "")),
                    deposit=self._parse_float(self._get_val(row, ["Deposit", "Security Deposit"], 0.0)),
                    parking=str(self._get_val(row, ["Parking", "Parking Space"], "")),
                    comments=str(self._get_val(row, ["Comments", "Comment", "Coment", "Notes"], "")),
                    source_file=filename,
                    floor=str(self._get_val(row, ["Floor", "Level"], ""))
            ))

        return rent_roll

    async def extract_rent_roll_from_excel(self, excel_content: bytes, total_units: int = 0, filename: str = None) -> List[RentRollItem]:
        """
        Extracts the rent roll from an Excel file (bytes).
        Async version that works with file content in memory.
        """
        import logging
        import io
        logger = logging.getLogger(__name__)
        
        try:
            # Load Excel File
            xls = pd.ExcelFile(io.BytesIO(excel_content))
            
            best_rent_roll = []
            best_sheet_name = ""
            
            # Iterate through all sheets
            for sheet_name in xls.sheet_names:
                try:
                    df = pd.read_excel(xls, sheet_name=sheet_name, header=None)
                    if df.empty:
                        continue
                        
                    # Find Header Row
                    header_row_idx = None
                    for i, row in df.iterrows():
                        if i > 30: break
                        
                        row_str = []
                        for x in row.tolist():
                            s = str(x).lower().strip()
                            if s in ['nan', 'none', '', 'nat']:
                                s = ""
                            row_str.append(s)

                        # Check identifiers
                        unit_indices = [idx for idx, x in enumerate(row_str) if any(k in x for k in ["unit", "apt", "apartment", "suite", "#"]) and len(x) < 30]
                        rent_indices = [idx for idx, x in enumerate(row_str) if any(k in x for k in ["rent", "month", "amount", "rate", "price"]) and len(x) < 30]
                        
                        if len(unit_indices) > 0 and len(rent_indices) > 0:
                            all_indices = set(unit_indices + rent_indices)
                            if len(all_indices) >= 2:
                                header_row_idx = i
                                break
                    
                    if header_row_idx is None:
                        continue
                    
                    # Reload with correct header
                    df_data = pd.read_excel(xls, sheet_name=sheet_name, header=header_row_idx)
                    df_data = df_data.fillna("")
                    
                    current_sheet_roll = []
                    for _, row in df_data.iterrows():
                        # Use case-insensitive lookup
                        unit_number = str(self._get_val(row, ["Unit Number", "Unit #", "Unit", "Apt No"], ""))
                        tenant_name = str(self._get_val(row, ["Tenant Name", "Tenant", "Resident", "Tenant(s)", "Name"], ""))
                        
                        if not unit_number and not tenant_name:
                            continue
                        
                        if str(unit_number).lower() in ["total", "totals", "average", "averages", "nan", ""]:
                            continue

                        # Skip rows where unit number is too long (likely a note)
                        if len(unit_number) > 20:
                            continue
                        
                        try:
                            current_sheet_roll.append(RentRollItem(
                                unit_number=unit_number,
                                unit_type=str(self._get_val(row, ["Unit Type", "Type", "Floor Plan", "Occupancy Type"], "")),
                                unit_size=self._parse_int(self._get_val(row, ["Unit Size", "Sq Ft", "Square Feet", "SF", "Size", "Area"], 0)),
                                tenant_name=tenant_name,
                                current_rent=self._parse_float(self._get_val(row, ["Rent Amount", "Current Rent", "Rent", "Total Rent", "$/Month", "Rate", "2024 Rent"], 0.0)),
                                stabilized_rent=self._parse_float(self._get_val(row, ["Stabilized Rent", "Stabilized"], 0.0)),
                                market_rent=self._parse_float(self._get_val(row, ["Market Rent", "Market", "Pro Forma"], 0.0)),
                                move_in_date=str(self._get_val(row, ["Move In Date", "Move-In Date", "Move In"], "")),
                                lease_start=str(self._get_val(row, ["Lease Start", "Lease Start Date", "Start", "Start Date"], "")),
                                lease_end=str(self._get_val(row, ["Lease End", "Lease End Date", "End", "End Date", "Lease Exp"], "")),
                                deposit=self._parse_float(self._get_val(row, ["Deposit", "Security Deposit", "Sec Dep"], 0.0)),
                                parking=str(self._get_val(row, ["Parking", "Parking Space", "Parking Space #"], "")),
                                comments=str(self._get_val(row, ["Comments", "Comment", "Coment", "Notes"], "")),
                                source_file=f"{filename} | Sheet: {sheet_name}",
                                floor=str(self._get_val(row, ["Floor", "Level"], ""))
                            ))
                        except Exception as e:
                            # logger.warning(f"Failed to parse rent roll row: {e}")
                            continue
                    
                    if len(current_sheet_roll) > len(best_rent_roll):
                        best_rent_roll = current_sheet_roll
                        best_sheet_name = sheet_name
                        
                except Exception as e:
                    logger.warning(f"Failed to process sheet {sheet_name}: {e}")
                    continue
            
            if best_rent_roll:
                logger.info(f"Extracted {len(best_rent_roll)} rent roll items from Excel file {filename} (Sheet: {best_sheet_name})")
                return best_rent_roll
            else:
                logger.warning(f"Could not find Rent Roll headers in any sheet of {filename}")
                return []
                
        except Exception as e:
            logger.error(f"Failed to extract rent roll from Excel: {e}")
            return []

    async def extract_property_meta_from_pdf(self, pdf_content: bytes) -> PropertyMeta:
        """
        Extracts property metadata from a PDF document (bytes).
        """
        import logging
        logger = logging.getLogger(__name__)

        property_meta_prompt = """
        Extract the property address, year built, purchase price, total units, current_loan_balance, AND building_size from the document.
        
        CRITICAL INSTRUCTIONS FOR PURCHASE PRICE:
        - Look for "Purchase Price", "Asking Price", "Offering Price", "Price", "Guidance", "Pricing", "Market Value", or "Request for Offers".
        - It is often on the cover page or Executive Summary.
        - If a range is given (e.g., $10M - $11M), use the lower bound ($10M).
        - If "Unpriced", "TBD", or "Best Offer", look for a "Strike Price" or "Guidance" elsewhere. If still not found, return 0.0.
        
        CRITICAL INSTRUCTIONS FOR EXISTING LOAN:
        - Look for "Existing Loan", "Current Debt", "Loan Balance", "Assumable Debt", or "Principal Balance".

        CRITICAL INSTRUCTIONS FOR BUILDING SIZE:
        - Look for "Rentable SF", "NRA", "Net Rentable Area", "Gross Building Area", "Building Size", "Total SF", or "Square Feet".
        - This represents the total square footage of the building(s).
        
        Return a single JSON object with the following keys: "address", "year_built", "purchase_price", "total_units", "current_loan_balance", "building_size".

        Example:
        {
            "address": "123 Main St, Anytown, USA",
            "year_built": 2022,
            "purchase_price": 5000000.0,
            "total_units": 50,
            "current_loan_balance": 7200000.0,
            "building_size": 45000
        }
        """
        
        try:
            property_meta_data = self.gemini_client.generate_structured_data(
                property_meta_prompt,
                pydantic_schema=PropertyMeta,
                pdf_data=pdf_content,
                expect_list=False
            )

            # Sanity Check for Purchase Price Hallucination
            # Use 0 as default if key is missing or None
            purchase_price = property_meta_data.get("purchase_price") or 0
            total_units = property_meta_data.get("total_units") or 0
            
            # FIX: Stronger Sanity Check for Purchase Price
            # If price < $100k, it's almost certainly wrong (e.g. deposit, fee, or per unit price extraction error).
            if purchase_price > 0 and purchase_price < 100_000:
                 logger.warning(f"Voided suspiciously low Purchase Price of ${purchase_price} (<$100k). Resetting to 0.")
                 property_meta_data["purchase_price"] = 0.0
            # If > 4 units and price < $500k, it's likely a deposit or per-unit price error
            elif purchase_price > 0 and purchase_price < 500_000 and total_units > 4:
                logger.warning(f"Voided suspiciously low Purchase Price of ${purchase_price} for {total_units} units. Resetting to 0.")
                property_meta_data["purchase_price"] = 0.0
            elif purchase_price > 0 and purchase_price < 1_000_000 and total_units > 10:
                logger.warning(f"Voided suspiciously low Purchase Price of ${purchase_price} for {total_units} units. Resetting to 0.")
                property_meta_data["purchase_price"] = 0.0
            
            # Robustness check
            if not isinstance(property_meta_data, dict) or "address" not in property_meta_data:
                logger.warning(f"Failed to extract valid Property Meta from PDF. Data: {property_meta_data}")
                return PropertyMeta(address="Unknown", year_built=1980, purchase_price=0.0, total_units=0)
                
            return PropertyMeta(**property_meta_data)
            
        except Exception as e:
            logger.error(f"Failed to extract property meta from PDF: {e}")
            return PropertyMeta(address="Unknown", year_built=1980, purchase_price=0.0, total_units=0)

    async def extract_rent_roll_from_pdf(self, pdf_content: bytes, total_units: int = 0, filename: str = None) -> List[RentRollItem]:
        """
        Extracts the rent roll from a PDF document (bytes).
        """
        import logging
        logger = logging.getLogger(__name__)
        
        # We need raw text for the prompt context, but Gemini Vision handles PDF bytes directly better for tables.
        # However, generate_structured_data usually expects text + optional pdf_data.
        # Let's try to get some text if possible, or just use a generic prompt with the PDF.
        
        # If we don't have text, we can just pass the prompt.
        unit_count_str = f"for {total_units} units" if total_units > 0 else ""
        
        rent_roll_prompt = f"""
        Extract the rent roll from the document {unit_count_str}.
        
        CRITICAL FOR UNIT TYPE:
        - Extract the Unit Type EXACTLY as it appears in the document.
        - Do NOT normalize, translate, or convert it.
        - Examples: Keep "0/1.00", "2/1.00", "VACANT", "1 BR", "2 BDRM" exactly as written.
        
        CRITICAL FOR MARKET RENT:
        - Look for "Market Rent", "Pro Forma Rent", "Potential Rent", or "Street Rent".
        - If Market Rent is not explicitly listed for a unit, DO NOT invent one. Return null or 0.0.
        
        CRITICAL FOR STABILIZED RENT:
        - Look for "Stabilized Rent" or "Stabilized".
        - If not explicitly listed, return 0.0.

        CRITICAL FOR UNIT SIZE:
        - Look for "Unit Size", "Sq Ft", "Square Feet", or "SF".

        OPTIONAL FIELDS:
        - "deposit": Security deposit amount.
        - "parking": Parking space number or fee.
        - "comments": Any notes or comments.

        Return a JSON array of objects, where each object has the following keys: "unit_number", "unit_type", "unit_size" (integer), "tenant_name", "current_rent", "stabilized_rent", "market_rent", "move_in_date", "lease_start", "lease_end", "deposit", "parking", "comments".
        """
        
        try:
            # Use generate_structured_data_async instead of synchronous version
            rent_roll_data = await self.gemini_client.generate_structured_data_async(
                rent_roll_prompt,
                pydantic_schema=RentRollItem,
                pdf_data=pdf_content,
                expect_list=True
            )
            
            rent_roll = self.normalization_service.normalize_rent_roll(rent_roll_data)
            if filename:
                for item in rent_roll:
                    item.source_file = filename
            return rent_roll
        except Exception as e:
            logger.error(f"Failed to extract rent roll from PDF: {e}")
            return []

    async def ingest_pdf_document(self, document_id: str) -> UnderwritingAnalysis:
        """
        Ingests a PDF document from the ocr-backend using parallel processing.
        """
        import asyncio
        import logging
        logging.basicConfig(level=logging.INFO)
        logger = logging.getLogger(__name__)

        # 1. Wait for Processing
        max_wait_time = 300
        elapsed_time = 0
        mime_type = "application/pdf"
        while elapsed_time < max_wait_time:
            status = await self.ocr_backend_client.get_document_status(document_id)
            if status["status"] == "completed":
                mime_type = status.get("mime_type", "application/pdf")
                break
            await asyncio.sleep(5)
            elapsed_time += 5
        else:
            raise HTTPException(status_code=408, detail="Document processing timed out.")

        # 2. Handle Excel Files Special Case
        if mime_type in ["application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", "application/vnd.ms-excel"]:
            logger.info(f"Processing Excel document {document_id}")
            try:
                file_bytes = await self.ocr_backend_client.get_document_bytes(document_id)
                
                # 1. Fetch "Text" content which is now a markdown/CSV representation of all sheets
                # This allows us to try LLM extraction on Excel data if direct parsing fails or for other data types
                excel_text_repr = await self.ocr_backend_client.get_document_text(document_id)
                
                # 2. Try Direct Excel Parsing First (High Confidence)
                rent_roll = await self.extract_rent_roll_from_excel(file_bytes, filename=f"doc_{document_id}.xlsx")
                
                # 3. If Direct Parsing yields nothing, try LLM extraction on the text representation
                # This handles complex/messy Excel files that don't match standard Rent Roll formats
                if not rent_roll and excel_text_repr:
                    logger.info("Direct Excel parsing failed or yielded no units. Attempting LLM extraction on Excel text representation.")
                    # Use a specialized prompt for Excel text representation
                    rent_roll_prompt = """
                    Extract the rent roll from this Excel file content.
                    The content is presented as text/CSV from multiple sheets.
                    
                    CRITICAL: Look for rows representing rental units.
                    Ignore headers, summaries, or total lines.
                    
                    Return a JSON array of objects with keys: "unit_number", "unit_type", "unit_size", "tenant_name", "current_rent", "market_rent", "move_in_date", "lease_start", "lease_end".
                    """
                    try:
                        rent_roll_data = await self.gemini_client.generate_structured_data_async(
                            f"{rent_roll_prompt}\n\n{excel_text_repr}",
                            pydantic_schema=RentRollItem,
                            expect_list=True
                        )
                        rent_roll = self.normalization_service.normalize_rent_roll(rent_roll_data)
                    except Exception as llm_e:
                        logger.warning(f"LLM extraction from Excel text failed: {llm_e}")

                rent_roll_summary = self._summarize_rent_roll(rent_roll)
                
                # 4. Try to extract Property Meta from Excel text representation if available
                property_meta = PropertyMeta(
                    address="Extracted from Rent Roll Excel",
                    year_built=0,
                    purchase_price=0.0,
                    total_units=len(rent_roll),
                    current_loan_balance=0.0,
                    building_size=0
                )
                
                if excel_text_repr:
                    try:
                        meta_prompt = "Extract property address, total units, and any financial info from this Excel content."
                        extracted_meta = await self.gemini_client.generate_structured_data_async(
                            f"{meta_prompt}\n\n{excel_text_repr}",
                            pydantic_schema=PropertyMeta,
                            expect_list=False
                        )
                        # Merge with default
                        if isinstance(extracted_meta, dict):
                            # Clean up dict to match PropertyMeta
                            valid_keys = PropertyMeta.__fields__.keys()
                            clean_meta = {k: v for k, v in extracted_meta.items() if k in valid_keys}
                            property_meta = property_meta.copy(update=clean_meta)
                            # Ensure total_units is consistent if we found rent roll items
                            if len(rent_roll) > 0:
                                property_meta.total_units = len(rent_roll)
                    except Exception as e:
                        logger.warning(f"Failed to extract meta from Excel text: {e}")

                # Create Analysis Object with Excel Data
                analysis = UnderwritingAnalysis(
                    document_id=document_id,
                    pass_fail_status="PASS",
                    property_meta=property_meta,
                    rent_roll=rent_roll,
                    rent_roll_summary=rent_roll_summary,
                    historical_expenses=[],
                    audit_trail=[{
                        "field_name": "Rent Roll Extraction",
                        "extracted_value": f"{len(rent_roll)} units",
                        "source": "Excel File",
                        "confidence_score": 1.0 if rent_roll else 0.0,
                        "method": "Direct Excel Parsing + LLM Fallback",
                        "document_id": document_id
                    }],
                    om_proforma=[],
                    tax_assumptions=None
                )
                return analysis
                
            except Exception as e:
                logger.error(f"Failed to process Excel document: {e}")
                raise HTTPException(status_code=500, detail=f"Failed to process Excel document: {str(e)}")

        # 3. Fetch Prerequisites (Text & PDF Bytes)
        # We need these before we can start parallel tasks
        try:
            raw_text, pdf_bytes = await asyncio.gather(
                self.ocr_backend_client.get_document_text(document_id),
                self.ocr_backend_client.get_document_bytes(document_id)
            )
        except Exception as e:
            logger.error(f"Failed to fetch document content: {e}")
            raise HTTPException(status_code=500, detail="Failed to fetch document content")

        if not pdf_bytes:
             raise HTTPException(status_code=400, detail="Failed to fetch PDF content from OCR backend.")

        # 4. Define Async Tasks for Parallel Execution
        
        # Task A: Property Meta
        async def task_property_meta():
            logger.info(f"Starting Property Meta Extraction. Raw text length: {len(raw_text)}")
            property_meta_prompt = """
            Extract the property address, year built, purchase price, total units, current_loan_balance, AND building_size from the document.
            
            CRITICAL INSTRUCTIONS FOR PURCHASE PRICE:
            - Look for "Purchase Price", "Asking Price", "Offering Price", "Price", "Guidance", "Pricing", "Market Value", or "Request for Offers".
            - If a range is given (e.g., $10M - $11M), use the lower bound ($10M).
            - If "Unpriced", "TBD", or "Best Offer", return 0.0.
            
            CRITICAL INSTRUCTIONS FOR EXISTING LOAN:
            - Look for "Existing Loan", "Current Debt", "Loan Balance", "Assumable Debt", or "Principal Balance".
            
            CRITICAL INSTRUCTIONS FOR BUILDING SIZE:
            - Look for "Rentable SF", "NRA", "Net Rentable Area", "Gross Building Area", "Building Size", "Total SF", or "Square Feet".
            
            Return a single JSON object with the following keys: "address", "year_built", "purchase_price", "total_units", "current_loan_balance", "building_size".
            """
            try:
                property_meta_data = await self.gemini_client.generate_structured_data_async(
                    f"{property_meta_prompt}\n\n{raw_text}",
                    pydantic_schema=PropertyMeta,
                    expect_list=False
                )
                
                logger.info(f"Raw Property Meta Data Extracted: {property_meta_data}")

                # Sanity Check for Purchase Price Hallucination
                # Use 0 as default if key is missing or None
                purchase_price = property_meta_data.get("purchase_price") or 0
                total_units = property_meta_data.get("total_units") or 0
                
                # FIX: Stronger Sanity Check for Purchase Price (Duplicate logic for async path)
                if purchase_price > 0 and purchase_price < 100_000:
                     logger.warning(f"Voided suspiciously low Purchase Price of ${purchase_price} (<$100k). Resetting to 0.")
                     property_meta_data["purchase_price"] = 0.0
                # If > 4 units and price < $500k, it's likely a deposit or per-unit price error
                elif purchase_price > 0 and purchase_price < 500_000 and total_units > 4:
                    logger.warning(f"Voided suspiciously low Purchase Price of ${purchase_price} for {total_units} units. Resetting to 0.")
                    property_meta_data["purchase_price"] = 0.0
                elif purchase_price > 0 and purchase_price < 1_000_000 and total_units > 10:
                    logger.warning(f"Voided suspiciously low Purchase Price of ${purchase_price} for {total_units} units. Resetting to 0.")
                    property_meta_data["purchase_price"] = 0.0

                # Robustness check
                if not isinstance(property_meta_data, dict) or "address" not in property_meta_data:
                     # Check for dict with error
                     if isinstance(property_meta_data, dict) and "error" in property_meta_data:
                         logger.warning(f"Property Meta Extraction Error: {property_meta_data}")
                     # Return default
                     return PropertyMeta(address="Unknown", year_built=1980, purchase_price=0.0, total_units=0)
                
                return PropertyMeta(**property_meta_data)
            except Exception as e:
                logger.error(f"Failed to extract property meta: {e}")
                return PropertyMeta(address="Unknown", year_built=1980, purchase_price=0.0, total_units=0)

        # Task B: Raw Expenses (T12) - Use FAST Model
        async def task_raw_expenses():
            try:
                return await self.ingest_financials_from_pdf(document_id, use_fast_model=True)
            except Exception as e:
                logger.error(f"Failed to extract financials: {e}")
                return []

        # Task C: P&L Income (Total) - Use FAST Model
        async def task_pnl_income():
            try:
                return await self.ingest_income_statement_from_pdf(document_id, use_fast_model=True)
            except Exception as e:
                logger.error(f"Failed to extract P&L income: {e}")
                return 0.0

        # Task D: OM Proforma (Text Based)
        async def task_om_proforma():
            try:
                # Use synchronous OM scraper but run in thread pool if needed,
                # but extract_proforma is regex based so fast enough.
                # However, if it fails, it calls gemini which is async?
                # Wait, extract_proforma is purely regex. extract_om_proforma_from_pdf is async.
                
                proforma = self.om_scraper_service.extract_proforma(raw_text)
                if not proforma:
                    # Fallback to vision
                    file_ext = "pdf" if mime_type == "application/pdf" else mime_type.split("/")[-1]
                    proforma = await self.om_scraper_service.extract_om_proforma_from_file(pdf_bytes, f"doc_{document_id}.{file_ext}", mime_type=mime_type)
                return proforma
            except Exception as e:
                logger.error(f"Failed to extract OM Proforma: {e}")
                return []

        # Task E: Tax Assumptions
        async def task_tax_assumptions():
            try:
                return self.om_scraper_service.extract_tax_assumptions(raw_text)
            except Exception as e:
                logger.error(f"Failed to extract tax assumptions: {e}")
                return None

        # 5. Execute Phase 1 Parallel Tasks
        logger.info("Starting Phase 1 Parallel Extraction...")
        results_phase1 = await asyncio.gather(
            task_property_meta(),
            task_raw_expenses(),
            task_pnl_income(),
            task_om_proforma(),
            task_tax_assumptions()
        )
        
        property_meta, raw_expenses, pnl_income, om_proforma, tax_assumptions = results_phase1
        logger.info(f"Phase 1 Complete. Extracted Property: {property_meta.address}, Expenses: {len(raw_expenses)}")

        # 6. Execute Phase 2 Parallel Tasks (Dependent on Property Meta)
        # Rent Roll extraction relies on total_units from property_meta for better context
        
        async def task_rent_roll():
            # Rent Roll is complex, so we stick to the PRO model for accuracy,
            # unless we find it's too slow and simple enough for FAST.
            # Keeping PRO for now as Rent Roll accuracy is critical.
            rent_roll_prompt = f"""
            Extract the rent roll from the document for {property_meta.total_units} units.
            
            CRITICAL FOR UNIT TYPE:
            - Extract the Unit Type EXACTLY as it appears in the document.
            - Do NOT normalize, translate, or convert it.
            
            CRITICAL FOR MARKET RENT:
            - Look for "Market Rent", "Pro Forma Rent", "Potential Rent", or "Street Rent".
            - If Market Rent is not explicitly listed for a unit, DO NOT invent one. Return null or 0.0.
            
            CRITICAL FOR STABILIZED RENT:
            - Look for "Stabilized Rent" or "Stabilized".
            - If not explicitly listed, return 0.0.

            CRITICAL FOR UNIT SIZE:
            - Look for "Unit Size", "Sq Ft", "Square Feet", "SF", or just "Size".
            - If Unit Size is missing, return 0.

            CRITICAL FOR GENERIC RENT:
            - If a column is just labeled "Rent", treat it as "Current Rent".
            
            OPTIONAL FIELDS:
            - "deposit": Security deposit amount.
            - "parking": Parking space number or fee.
            - "comments": Any notes or comments.
            - "floor": Floor number/level (e.g. "1st", "2nd").

            Return a JSON array of objects, where each object has the following keys: "unit_number", "unit_type", "unit_size" (integer), "tenant_name", "current_rent", "stabilized_rent", "market_rent", "move_in_date", "lease_start", "lease_end", "deposit", "parking", "comments", "floor".
            """
            try:
                rent_roll_data = await self.gemini_client.generate_structured_data_async(
                    f"{rent_roll_prompt}\n\n{raw_text}",
                    pydantic_schema=RentRollItem,
                    pdf_data=pdf_bytes,
                    expect_list=True,
                    mime_type=mime_type
                )
                return self.normalization_service.normalize_rent_roll(rent_roll_data)
            except Exception as e:
                logger.error(f"Failed to extract Rent Roll: {e}")
                return []

        async def task_normalize_expenses():
            # Run normalization on the raw expenses extracted in Phase 1
            return await self.normalization_service.normalize_expenses_async(raw_expenses, document_id=document_id)

        logger.info("Starting Phase 2 Parallel Extraction (Rent Roll & Normalization)...")
        results_phase2 = await asyncio.gather(
            task_rent_roll(),
            task_normalize_expenses()
        )
        
        rent_roll, historical_expenses = results_phase2
        logger.info(f"Phase 2 Complete. Rent Roll Items: {len(rent_roll)}, Normalized Expenses: {len(historical_expenses)}")

        # 7. Post-Processing & Aggregation
        rent_roll_summary = self._summarize_rent_roll(rent_roll)
        
        # FIX: Sync Property Meta Total Units with Actual Extracted Rent Roll Count
        # If we extracted units from the Rent Roll, that count is the source of truth.
        if len(rent_roll) > 0 and property_meta.total_units != len(rent_roll):
            logger.info(f"Updating Property Meta Total Units from {property_meta.total_units} to {len(rent_roll)} based on Rent Roll extraction.")
            property_meta.total_units = len(rent_roll)

        # 8. Build Audit Trail
        audit_trail_entries = []
        
        # Property Meta Logs
        audit_trail_entries.extend([
            {"field_name": "Property Address", "extracted_value": property_meta.address, "source": "OM / PDF", "confidence_score": 0.9, "method": "Extracted from OM cover page", "document_id": document_id},
            {"field_name": "Year Built", "extracted_value": property_meta.year_built, "source": "OM / PDF", "confidence_score": 0.9, "method": "Extracted from property description", "document_id": document_id},
            {"field_name": "Building Size (Sq Ft)", "extracted_value": property_meta.building_size, "source": "OM / PDF", "confidence_score": 0.9, "method": "Extracted from property description", "document_id": document_id},
            {"field_name": "Purchase Price", "extracted_value": property_meta.purchase_price, "source": "OM / PDF", "confidence_score": 0.9, "method": "Extracted from offering summary", "document_id": document_id},
            {"field_name": "Total Units", "extracted_value": property_meta.total_units, "source": "Rent Roll / PDF", "confidence_score": 0.95, "method": f"Counted {len(rent_roll)} units from rent roll", "document_id": document_id}
        ])
        
        # Rent Roll Logs
        audit_trail_entries.extend([
            {"field_name": "Occupancy Rate", "extracted_value": f"{rent_roll_summary.occupancy_rate:.2%}", "source": "Rent Roll / PDF", "confidence_score": 0.98, "method": f"Calculated from {rent_roll_summary.occupied_units} occupied / {rent_roll_summary.total_units} total", "document_id": document_id},
            {"field_name": "Total Annual Rent (T12)", "extracted_value": rent_roll_summary.total_annual_rent, "source": "Rent Roll / PDF", "confidence_score": 0.98, "method": "Summed current rents", "document_id": document_id}
        ])
        
        # Expense Logs
        for normalized_exp in historical_expenses:
            if normalized_exp.audit_log:
                audit_trail_entries.append(normalized_exp.audit_log.model_dump())

        # 9. Create Analysis Object
        analysis = UnderwritingAnalysis(
            document_id=document_id,
            pass_fail_status="PASS",
            property_meta=property_meta,
            rent_roll=rent_roll,
            rent_roll_summary=rent_roll_summary,
            historical_expenses=historical_expenses,
            audit_trail=audit_trail_entries,
            om_proforma=om_proforma,
            tax_assumptions=tax_assumptions
        )
        
        # 10. Income Reconciliation Warning
        rent_roll_income = analysis.rent_roll_summary.total_annual_rent
        income_discrepancy_warning = self.compare_income_sources(rent_roll_income, pnl_income)
        
        if income_discrepancy_warning:
            analysis.gating_reasons.append(income_discrepancy_warning)
            audit_trail_entries.append({
                "field_name": "Income Source Reconciliation",
                "extracted_value": f"Rent Roll: ${rent_roll_income:,.2f}, P&L: ${pnl_income:,.2f}",
                "source": "Rent Roll vs. P&L",
                "confidence_score": 0.85,
                "method": income_discrepancy_warning
            })
        
        return analysis

    async def ingest_financials_from_pdf(self, document_id: str, use_fast_model: bool = False) -> List[Dict]:
        """
        Extracts raw T12 line items. We don't normalize yet, just get the text.
        """
        raw_text = await self.ocr_backend_client.get_document_text(document_id)
        
        prompt = """
        Analyze this T12 Income Statement. Extract all EXPENSE line items.
        Ignore Income line items.
        
        CRITICAL FOR AMOUNTS:
        - If the amount is in parentheses like (500), it is a positive expense.
        - If the amount has a minus sign like -500, it is a positive expense.
        - Return the absolute value of the expense.
        
        Return a JSON array: [{"description": "Repair - Plumbing", "amount": 500.00}, ...]
        """

        # Use async
        raw_expenses = await self.gemini_client.generate_structured_data_async(
            f"{prompt}\n\n{raw_text}",
            pdf_data=None,
            use_fast_model=use_fast_model
        )
        return raw_expenses

    async def ingest_income_statement_from_pdf(self, document_id: str, use_fast_model: bool = False) -> float:
        """
        Extracts the total annual income from a T12 Income Statement.
        """
        raw_text = await self.ocr_backend_client.get_document_text(document_id)

        prompt = """
        Analyze this T12 Income Statement. Find the TOTAL ANNUAL INCOME.
        Return a single JSON object with one key, "total_annual_income".
        Example: {"total_annual_income": 1250000.00}
        """

        # Use async
        income_data = await self.gemini_client.generate_structured_data_async(
            f"{prompt}\n\n{raw_text}",
            pdf_data=None,
            expect_list=False,
            use_fast_model=use_fast_model
        )
        
        if isinstance(income_data, dict):
            return income_data.get("total_annual_income", 0.0)
        return 0.0

    def compare_income_sources(self, rent_roll_income: float, pnl_income: float, threshold: float = 0.05) -> Optional[str]:
        """
        Compares the total annual income from the rent roll and the P&L.
        Returns a warning string if the discrepancy is above the threshold.
        """
        if not pnl_income or not rent_roll_income:
            return "Could not verify income from both Rent Roll and P&L."

        discrepancy = abs(rent_roll_income - pnl_income) / pnl_income
        if discrepancy > threshold:
            return f"Warning: Annual income from Rent Roll (${rent_roll_income:,.2f}) and P&L (${pnl_income:,.2f}) differs by {discrepancy:.2%}, which is above the {threshold:.2%} threshold."
        return None

    def _summarize_rent_roll(self, rent_roll: List[RentRollItem]) -> RentRollSummary:
        """
        Summarizes the rent roll to calculate total units, occupancy rate, and rent totals.
        """
        total_units = len(rent_roll)

        # Calculate Occupied Units (Check if tenant name exists and is not N/A)
        occupied_units = sum(1 for item in rent_roll if item.tenant_name and item.tenant_name.lower() not in ["n/a", "", "vacant"] and item.current_rent and item.current_rent > 0)
        
        # Calculate SF for occupied units (for accurate Avg Rent/SF)
        occupied_sf = sum((item.unit_size or 0) for item in rent_roll if item.tenant_name and item.tenant_name.lower() not in ["n/a", "", "vacant"] and item.current_rent and item.current_rent > 0)

        occupancy_rate = occupied_units / total_units if total_units > 0 else 0.0

        # Calculate Totals
        total_unit_size = sum((item.unit_size or 0) for item in rent_roll)
        total_monthly_rent = sum((item.current_rent or 0.0) for item in rent_roll)
        total_stabilized_rent = sum((item.stabilized_rent or 0.0) for item in rent_roll)
        total_market_rent = sum((item.market_rent or 0.0) for item in rent_roll)

        total_annual_rent = total_monthly_rent * 12

        # Averages
        avg_unit_size = total_unit_size / total_units if total_units > 0 else 0
        
        # Modified to use occupied units/sf for Current Rent averages (ignore 0$ rent)
        avg_rent_per_unit = total_monthly_rent / occupied_units if occupied_units > 0 else 0
        avg_rent_per_sf = total_monthly_rent / occupied_sf if occupied_sf > 0 else 0

        avg_stabilized_per_unit = total_stabilized_rent / total_units if total_units > 0 else 0
        avg_stabilized_per_sf = total_stabilized_rent / total_unit_size if total_unit_size > 0 else 0

        avg_market_per_unit = total_market_rent / total_units if total_units > 0 else 0
        avg_market_per_sf = total_market_rent / total_unit_size if total_unit_size > 0 else 0

        return RentRollSummary(
            total_units=total_units,
            occupied_units=occupied_units,
            occupancy_rate=occupancy_rate,
            avg_unit_size=avg_unit_size,
            total_monthly_rent=total_monthly_rent,
            total_annual_rent=total_annual_rent,
            total_stabilized_rent=total_stabilized_rent,
            total_market_rent=total_market_rent,
            avg_rent_per_unit=avg_rent_per_unit,
            avg_rent_per_sf=avg_rent_per_sf,
            avg_stabilized_per_unit=avg_stabilized_per_unit,
            avg_stabilized_per_sf=avg_stabilized_per_sf,
            avg_market_per_unit=avg_market_per_unit,
            avg_market_per_sf=avg_market_per_sf
        )



# import json
# import pandas as pd
# from typing import List, Dict, Any
# from fastapi import HTTPException
# from app.models.schemas import RentRollItem, PropertyMeta, UnderwritingAnalysis, RentRollSummary
# from app.services.normalization_service import NormalizationService
# from app.services.gemini_client import GeminiClient
# from app.services.ocr_backend_client import OcrBackendClient
# from datetime import datetime

# class IngestionService:
#     def __init__(self):
#         self.gemini_client = GeminiClient()
#         self.normalization_service = NormalizationService(llm_service=self.gemini_client)
#         self.ocr_backend_client = OcrBackendClient()

#     async def ingest_pdf_document(self, document_id: str) -> UnderwritingAnalysis:
#         import asyncio
#         max_wait_time = 300  # 5 minutes
#         elapsed_time = 0
#         while elapsed_time < max_wait_time:
#             status = await self.ocr_backend_client.get_document_status(document_id)
#             if status["status"] == "completed":
#                 break
#             await asyncio.sleep(5)  # Use asyncio.sleep for non-blocking wait
#             elapsed_time += 5
#         else:
#             raise HTTPException(status_code=408, detail="Document processing timed out.")

#         raw_text = await self.ocr_backend_client.get_document_text(document_id)

#         # 1. Extract PropertyMeta (SAFE METHOD)
#         property_meta_prompt = """
#         Extract the property address, year built, purchase price, total units, AND current_loan_balance from the document.
#         Return a single JSON object with the following keys: "address", "year_built", "purchase_price", "total_units", "current_loan_balance".

#         Example:
#         {
#             "address": "123 Main St, Anytown, USA",
#             "year_built": 2022,
#             "purchase_price": 5000000.0,
#             "total_units": 50,
#             "current_loan_balance": 7200000.0
#         }
#         """
#         property_meta_data = self.gemini_client.generate_structured_data(
#             f"{property_meta_prompt}\n\n{raw_text}",
#             expect_list=False
#         )
#         if not isinstance(property_meta_data, dict) or "address" not in property_meta_data:
#             if isinstance(property_meta_data, dict) and "error" in property_meta_data:
#                 raise HTTPException(status_code=422, detail=f"Failed to extract Property Meta: {property_meta_data['error']}")
#             raise HTTPException(status_code=422, detail="Failed to extract valid Property Meta from document.")
#         property_meta = PropertyMeta(**property_meta_data)

#         # 2. Extract RentRoll (SAFE METHOD)
#         rent_roll_prompt = f"""
#         Extract the rent roll from the document for {property_meta.total_units} units.
#         Return a JSON array of objects, where each object has the following keys: "unit_number", "unit_type", "tenant_name", "current_rent", "market_rent", "lease_start", "lease_end".
#         """
#         pdf_bytes = await self.ocr_backend_client.get_document_bytes(document_id)
#         if not pdf_bytes:
#             raise HTTPException(status_code=400, detail="Failed to fetch PDF content from OCR backend.")
#         rent_roll_data = self.gemini_client.generate_structured_data(
#             f"{rent_roll_prompt}\n\n{raw_text}", pdf_data=pdf_bytes, expect_list=True
#         )
#         rent_roll = self.normalization_service.normalize_rent_roll(rent_roll_data)

#         # 3. Extract Raw Expenses
#         raw_expenses = await self.ingest_financials(document_id, raw_text)
#         historical_expenses = self.normalization_service.normalize_expenses(raw_expenses)
        
#         rent_roll_summary = self._summarize_rent_roll(rent_roll)
        
#         # 4. Build Audit Trail (Standardized)
#         audit_trail = []
        
#         audit_trail.append({
#             "field_name": "Property Address", "extracted_value": property_meta.address,
#             "source": "OM", "method": "AI Extraction", "confidence_score": 0.9, "timestamp": datetime.now().isoformat()
#         })
#         audit_trail.append({
#             "field_name": "Year Built", "extracted_value": property_meta.year_built,
#             "source": "OM", "method": "AI Extraction", "confidence_score": 0.9, "timestamp": datetime.now().isoformat()
#         })
#         audit_trail.append({
#             "field_name": "Purchase Price", "extracted_value": property_meta.purchase_price,
#             "source": "OM", "method": "AI Extraction", "confidence_score": 0.9, "timestamp": datetime.now().isoformat()
#         })
#         audit_trail.append({
#             "field_name": "Total Units", "extracted_value": property_meta.total_units,
#             "source": "Rent Roll", "method": "Counted from rent roll entries", "confidence_score": 0.95, "timestamp": datetime.now().isoformat()
#         })
#         audit_trail.append({
#             "field_name": "Occupancy Rate", "extracted_value": f"{rent_roll_summary.occupancy_rate:.2%}",
#             "source": "Rent Roll", "method": f"Calculated from {rent_roll_summary.occupied_units}/{rent_roll_summary.total_units} units", "confidence_score": 0.98, "timestamp": datetime.now().isoformat()
#         })
#         audit_trail.append({
#             "field_name": "Total Annual Rent (T12)", "extracted_value": rent_roll_summary.total_annual_rent,
#             "source": "Rent Roll", "method": "Summed current rents", "confidence_score": 0.98, "timestamp": datetime.now().isoformat()
#         })
        
#         for exp in historical_expenses:
#             # Transfer log from Expense object to Main Audit Trail
#             audit_trail.append({
#                 "field_name": exp.audit_log.field_name,
#                 "extracted_value": exp.audit_log.extracted_value,
#                 "source": exp.audit_log.source,
#                 "method": exp.audit_log.method,
#                 "confidence_score": exp.audit_log.confidence_score,
#                 "timestamp": datetime.now().isoformat()
#             })

#         analysis = UnderwritingAnalysis(
#             document_id=document_id,
#             pass_fail_status="PASS",
#             property_meta=property_meta,
#             rent_roll=rent_roll,
#             rent_roll_summary=rent_roll_summary,
#             historical_expenses=historical_expenses,
#             audit_trail=audit_trail
#         )

#         pnl_income = await self.ingest_income_statement_from_pdf(document_id, raw_text)
#         rent_roll_income = analysis.rent_roll_summary.total_annual_rent
        
#         income_discrepancy_warning = self.compare_income_sources(
#             rent_roll_income, pnl_income
#         )
#         if income_discrepancy_warning:
#             analysis.gating_reasons.append(income_discrepancy_warning)
#             analysis.audit_trail.append({
#                 "field_name": "Income Reconciliation",
#                 "extracted_value": f"Rent Roll: ${rent_roll_income:,.2f}, P&L: ${pnl_income:,.2f}",
#                 "source": "Rent Roll vs. P&L",
#                 "method": income_discrepancy_warning,
#                 "confidence_score": 0.85,
#                 "timestamp": datetime.now().isoformat()
#             })
        
#         return analysis

#     async def ingest_financials(self, doc_id, text):
#         prompt = """
#         Analyze this T12 Income Statement. Extract all EXPENSE line items.
#         Ignore Income line items.
#         Return a JSON array: [{"description": "Repair - Plumbing", "amount": 500.00}, ...]
#         If the amount is in parentheses (500), treat it as a positive expense number.
#         """
#         return self.gemini_client.generate_structured_data(f"{prompt}\n{text}", expect_list=True)
    
#     async def ingest_income_statement_from_pdf(self, document_id: str, raw_text: str) -> float:
#         """
#         Extracts the total annual income from a T12 Income Statement.
#         """
#         prompt = """
#         Analyze this T12 Income Statement. Find the TOTAL ANNUAL INCOME.
#         Return a single JSON object with one key, "total_annual_income".
#         Example: {"total_annual_income": 1250000.00}
#         """
#         income_data = self.gemini_client.generate_structured_data(
#             f"{prompt}\n\n{raw_text}",
#             expect_list=False
#         )
#         if isinstance(income_data, dict):
#             return income_data.get("total_annual_income", 0.0)
#         return 0.0

#     def compare_income_sources(self, rent_roll_income: float, pnl_income: float, threshold: float = 0.05) -> str | None:
#         """
#         Compares the total annual income from the rent roll and the P&L.
#         Returns a warning string if the discrepancy is above the threshold.
#         """
#         if not pnl_income or not rent_roll_income:
#             return "Could not verify income from both Rent Roll and P&L."

#         discrepancy = abs(rent_roll_income - pnl_income) / pnl_income if pnl_income != 0 else 0
#         if discrepancy > threshold:
#             return f"Warning: Income from Rent Roll (${rent_roll_income:,.2f}) and P&L (${pnl_income:,.2f}) differs by {discrepancy:.2%}"
#         return None

#     def _summarize_rent_roll(self, rent_roll: List[RentRollItem]) -> RentRollSummary:
#         total = len(rent_roll)
#         occupied = sum(1 for r in rent_roll if r.tenant_name and r.tenant_name.lower() not in ["vacant", "n/a", ""])
#         monthly = sum(r.current_rent for r in rent_roll)
#         return RentRollSummary(
#             total_units=total,
#             occupied_units=occupied,
#             occupancy_rate=occupied/total if total else 0,
#             total_monthly_rent=monthly,
#             total_annual_rent=monthly * 12
#         )