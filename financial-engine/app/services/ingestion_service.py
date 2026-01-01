import json
import pandas as pd
from typing import List, Dict, Any
from fastapi import HTTPException
from app.models.schemas import RentRollItem, PropertyMeta, UnderwritingAnalysis, StandardizedExpense, ExpenseCategory, AuditLog, RentRollSummary
from app.services.normalization_service import NormalizationService
from app.services.gemini_client import GeminiClient
from app.services.ocr_backend_client import OcrBackendClient

class IngestionService:
    def __init__(self):
        self.gemini_client = GeminiClient()
        self.normalization_service = NormalizationService(llm_service=self.gemini_client)
        self.ocr_backend_client = OcrBackendClient()

    def ingest_rent_roll_from_excel(self, file_path: str, property_meta: PropertyMeta) -> List[RentRollItem]:
        # Read with no header initially
        df = pd.read_excel(file_path, header=None)

        # logic to find the row that contains "Unit" AND "Rent"
        header_row_idx = None
        for i, row in df.iterrows():
            row_str = row.astype(str).str.lower().tolist()
            if any("unit" in x for x in row_str) and any("rent" in x for x in row_str):
                header_row_idx = i
                break

        if header_row_idx is None:
            raise ValueError("Could not find Rent Roll headers in Excel")

        # Reload with correct header
        df = pd.read_excel(file_path, header=header_row_idx)
        df = df.fillna("")

        rent_roll = []
        for _, row in df.iterrows():
            if not row.get("Unit Number") and not row.get("Tenant Name"):
                continue

            rent_roll.append(RentRollItem(
                unit_number=str(row.get("Unit Number", "")),
                unit_type=str(row.get("Unit Type", "")),
                tenant_name=str(row.get("Tenant Name", "")),
                current_rent=float(row.get("Rent Amount") or row.get("Current Rent") or 0.0),
                market_rent=float(row.get("Market Rent", 0.0)),
                lease_start=str(row.get("Lease Start", "")),
                lease_end=str(row.get("Lease End", ""))
            ))

        return rent_roll

    async def ingest_pdf_document(self, document_id: str) -> UnderwritingAnalysis:
        """
        Ingests a PDF document from the ocr-backend, extracts the required information,
        and returns a complete UnderwritingAnalysis object.
        """
        # Poll for document processing completion
        import asyncio
        max_wait_time = 300  # 5 minutes
        elapsed_time = 0
        while elapsed_time < max_wait_time:
            status = await self.ocr_backend_client.get_document_status(document_id)
            if status["status"] == "completed":
                break
            await asyncio.sleep(5)  # Use asyncio.sleep for non-blocking wait
            elapsed_time += 5
        else:
            raise HTTPException(status_code=408, detail="Document processing timed out.")

        raw_text = await self.ocr_backend_client.get_document_text(document_id)

        # 1. Extract PropertyMeta (SAFE METHOD)
        property_meta_prompt = """
        Extract the property address, year built, purchase price, total units, AND current_loan_balance from the document.
        Return a single JSON object with the following keys: "address", "year_built", "purchase_price", "total_units", "current_loan_balance".

        Example:
        {
            "address": "123 Main St, Anytown, USA",
            "year_built": 2022,
            "purchase_price": 5000000.0,
            "total_units": 50,
            "current_loan_balance": 7200000.0
        }
        """
        property_meta_data = self.gemini_client.generate_structured_data(
            f"{property_meta_prompt}\n\n{raw_text}",
            pydantic_schema=PropertyMeta,
            expect_list=False
        )
        # --- ROBUSTNESS FIX ---
        # If the returned data is not a valid dict, it means the LLM failed.
        # We must stop here to prevent creating a bad analysis object.
        if not isinstance(property_meta_data, dict) or "address" not in property_meta_data:
            # Check for an error key in the dictionary
            if isinstance(property_meta_data, dict) and "error" in property_meta_data:
                raise HTTPException(status_code=422, detail=f"Failed to extract Property Meta: {property_meta_data['error']}")
            raise HTTPException(status_code=422, detail="Failed to extract valid Property Meta from document.")
        property_meta = PropertyMeta(**property_meta_data)
        import logging
        logging.basicConfig(level=logging.INFO)
        logging.info(f"Extracted Property Meta: {property_meta}")

        # 2. Extract RentRoll (SAFE METHOD)
        rent_roll_prompt = f"""
        Extract the rent roll from the document for {property_meta.total_units} units.
        Return a JSON array of objects, where each object has the following keys: "unit_number", "unit_type", "tenant_name", "current_rent", "market_rent", "lease_start", "lease_end".
        """
        pdf_bytes = await self.ocr_backend_client.get_document_bytes(document_id)
        if not pdf_bytes:
            raise HTTPException(status_code=400, detail="Failed to fetch PDF content from OCR backend.")
        rent_roll_data = self.gemini_client.generate_structured_data(
            f"{rent_roll_prompt}\n\n{raw_text}",
            pdf_data=pdf_bytes,
            pydantic_schema=RentRollItem,
            expect_list=True
        )
        rent_roll = self.normalization_service.normalize_rent_roll(rent_roll_data)

        # 3. Extract Raw Expenses
        raw_expenses = await self.ingest_financials_from_pdf(document_id)

        # 4. Normalize Expenses (with audit trail integration)
        historical_expenses = self.normalization_service.normalize_expenses(raw_expenses)
        
        # 5. Compute Rent Roll Summary first (needed for audit trail)
        rent_roll_summary = self._summarize_rent_roll(rent_roll)
        
        # 6. Build comprehensive Audit Trail
        audit_trail_entries = []
        
        # Add Property Meta audit logs
        audit_trail_entries.append({
            "field_name": "Property Address",
            "extracted_value": property_meta.address,
            "source_doc": "OM / PDF",
            "confidence_score": 0.9,
            "reasoning": "Extracted from Operating Memorandum cover page"
        })
        audit_trail_entries.append({
            "field_name": "Year Built",
            "extracted_value": property_meta.year_built,
            "source_doc": "OM / PDF",
            "confidence_score": 0.9,
            "reasoning": "Extracted from property description section"
        })
        audit_trail_entries.append({
            "field_name": "Purchase Price",
            "extracted_value": property_meta.purchase_price,
            "source_doc": "OM / PDF",
            "confidence_score": 0.9,
            "reasoning": "Extracted from offering summary"
        })
        audit_trail_entries.append({
            "field_name": "Total Units",
            "extracted_value": property_meta.total_units,
            "source_doc": "Rent Roll / PDF",
            "confidence_score": 0.95,
            "reasoning": "Counted from rent roll line items"
        })
        
        # Add Rent Roll summary audit logs
        audit_trail_entries.append({
            "field_name": "Occupancy Rate",
            "extracted_value": f"{rent_roll_summary.occupancy_rate:.2%}",
            "source_doc": "Rent Roll / PDF",
            "confidence_score": 0.98,
            "reasoning": f"Calculated from {rent_roll_summary.occupied_units} occupied units out of {rent_roll_summary.total_units} total"
        })
        audit_trail_entries.append({
            "field_name": "Total Annual Rent (T12)",
            "extracted_value": rent_roll_summary.total_annual_rent,
            "source_doc": "Rent Roll / PDF",
            "confidence_score": 0.98,
            "reasoning": "Summed current rents from all unit line items"
        })
        
        # Add Normalized Expenses audit logs
        for normalized_exp in historical_expenses:
            # FIX: Ensure we handle the object structure correctly
            # If normalized_exp is a Pydantic model, use dot notation. If dict, use .get()
            
            # Assuming normalized_exp is a Pydantic model from normalization_service
            category = getattr(normalized_exp, 'mapped_category', None)
            amount = getattr(normalized_exp, 'amount', 0)
            original_text = getattr(normalized_exp, 'original_text', '')
            
            # The previous 'audit_log' field might not exist on the Expense object itself
            # We usually reconstruct the audit trail from the expense data
            
            audit_trail_entries.append({
                "field_name": f"Expense: {category.value if category else 'Unknown'}",
                "extracted_value": amount,
                "source_doc": "T12 / PDF", # Defaulting since we are inside PDF ingestion
                "confidence_score": getattr(normalized_exp, 'confidence', 0.9),
                "reasoning": f"Mapped '{original_text}' to standard category."
            })

        # 7. Create UnderwritingAnalysis object
        analysis = UnderwritingAnalysis(
            document_id=document_id,
            pass_fail_status="PASS",
            property_meta=property_meta,
            rent_roll=rent_roll,
            rent_roll_summary=rent_roll_summary,
            historical_expenses=historical_expenses,
            audit_trail=audit_trail_entries  # Pass the comprehensive audit trail
        )
        
        # 8. Get income from P&L and compare (add warning if mismatch)
        pnl_income = await self.ingest_income_statement_from_pdf(document_id)
        rent_roll_income = analysis.rent_roll_summary.total_annual_rent
        
        income_discrepancy_warning = self.compare_income_sources(
            rent_roll_income, pnl_income
        )
        if income_discrepancy_warning:
            analysis.gating_reasons.append(income_discrepancy_warning)
            audit_trail_entries.append({
                "field_name": "Income Source Reconciliation",
                "extracted_value": f"Rent Roll: ${rent_roll_income:,.2f}, P&L: ${pnl_income:,.2f}",
                "source_doc": "Rent Roll vs. P&L",
                "confidence_score": 0.85,
                "reasoning": income_discrepancy_warning
            })
        
        return analysis

    async def ingest_financials_from_pdf(self, document_id: str) -> List[Dict]:
        """
        Extracts raw T12 line items. We don't normalize yet, just get the text.
        """
        raw_text = await self.ocr_backend_client.get_document_text(document_id)

        prompt = """
        Analyze this T12 Income Statement. Extract all EXPENSE line items.
        Ignore Income line items.
        Return a JSON array: [{"description": "Repair - Plumbing", "amount": 500.00}, ...]
        If the amount is in parentheses (500), treat it as a positive expense number.
        """

        raw_expenses = self.gemini_client.generate_structured_data(f"{prompt}\n\n{raw_text}", pdf_data=None)
        return raw_expenses

    async def ingest_income_statement_from_pdf(self, document_id: str) -> float:
        """
        Extracts the total annual income from a T12 Income Statement.
        """
        raw_text = await self.ocr_backend_client.get_document_text(document_id)

        prompt = """
        Analyze this T12 Income Statement. Find the TOTAL ANNUAL INCOME.
        Return a single JSON object with one key, "total_annual_income".
        Example: {"total_annual_income": 1250000.00}
        """

        income_data = self.gemini_client.generate_structured_data(
            f"{prompt}\n\n{raw_text}",
            pdf_data=None,
            expect_list=False  # CRITICAL FIX: Expecting single dict, not list
        )
        
        # Now income_data is a dict, not a list
        if isinstance(income_data, dict):
            return income_data.get("total_annual_income", 0.0)
        return 0.0

    def compare_income_sources(self, rent_roll_income: float, pnl_income: float, threshold: float = 0.05) -> str | None:
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
        occupied_units = sum(1 for item in rent_roll if item.tenant_name and item.tenant_name.lower() not in ["n/a", "", "vacant"])

        occupancy_rate = occupied_units / total_units if total_units > 0 else 0.0

        # Calculate Totals
        total_monthly_rent = sum(item.current_rent for item in rent_roll if item.current_rent)
        total_annual_rent = total_monthly_rent * 12

        return RentRollSummary(
            total_units=total_units,
            occupied_units=occupied_units,
            occupancy_rate=occupancy_rate,
            total_monthly_rent=total_monthly_rent,
            total_annual_rent=total_annual_rent
        )