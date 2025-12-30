import json
import pandas as pd
from typing import List, Dict, Any
from fastapi import HTTPException
from app.models.schemas import RentRollItem, PropertyMeta, UnderwritingAnalysis, FinancialLineItem, ExpenseCategory, AuditLog, RentRollSummary
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
        
        rent_roll = []
        for _, row in df.iterrows():
            rent_roll.append(RentRollItem(
                **row.to_dict()
            ))
            
        if len(rent_roll) != property_meta.total_units:
            raise ValueError(f"Unit count mismatch: {len(rent_roll)} in rent roll, {property_meta.total_units} in metadata")
            
        return rent_roll

    async def ingest_pdf_document(self, document_id: str) -> UnderwritingAnalysis:
        """
        Ingests a PDF document from the ocr-backend, extracts the required information,
        and returns a complete UnderwritingAnalysis object.
        """
        import asyncio
        
        # Poll for document processing completion (non-blocking)
        max_wait_time = 300  # 5 minutes max wait
        elapsed = 0
        while elapsed < max_wait_time:
            status = await self.ocr_backend_client.get_document_status(document_id)
            if status["status"] == "completed":
                break
            await asyncio.sleep(5)  # Non-blocking wait (was time.sleep which blocked event loop)
            elapsed += 5
        else:
            raise HTTPException(status_code=408, detail=f"Document processing timeout after {max_wait_time} seconds")

        raw_text = await self.ocr_backend_client.get_document_text(document_id)

        # 1. Extract PropertyMeta (SAFE METHOD)
        property_meta_prompt = """
        Extract the property address, year built, purchase price, and total units from the document.
        Return a single JSON object with the following keys: "address", "year_built", "purchase_price", "total_units".

        Example:
        {
            "address": "123 Main St, Anytown, USA",
            "year_built": 2022,
            "purchase_price": 5000000.0,
            "total_units": 50
        }
        """
        # USE THE HELPER YOU WROTE!
        try:
            property_meta_data = self.gemini_client.generate_structured_data(
                prompt=f"{property_meta_prompt}\n\n{raw_text}",
                pdf_data=None,
                pydantic_schema=PropertyMeta
            )
            if not property_meta_data or len(property_meta_data) == 0:
                raise ValueError("LLM did not return any data for Property Meta.")
            # generate_structured_data always returns a list
            property_meta = PropertyMeta(**property_meta_data[0])
        except (ValueError, IndexError, TypeError) as e:
            raise HTTPException(status_code=400, detail=f"Failed to extract valid Property Meta: {e}")

        # 2. Extract RentRoll (SAFE METHOD)
        rent_roll_prompt = f"""
        Extract the rent roll from the document for {property_meta.total_units} units.
        Return a JSON array of objects, where each object has the following keys: "unit_number", "unit_type", "tenant_name", "current_rent", "market_rent", "lease_start", "lease_end".

        Example:
        [
            {{
                "unit_number": "101",
                "unit_type": "1BD/1BA",
                "tenant_name": "John Doe",
                "current_rent": 2500.0,
                "market_rent": 2600.0,
                "lease_start": "2023-01-15",
                "lease_end": "2024-01-14"
            }}
        ]
        """
        try:
            rent_roll_data = self.gemini_client.generate_structured_data(
                prompt=f"{rent_roll_prompt}\n\n{raw_text}",
                pdf_data=None,
                pydantic_schema=RentRollItem
            )
            if not rent_roll_data or len(rent_roll_data) == 0:
                raise ValueError("LLM did not return any data for Rent Roll.")
            # generate_structured_data always returns a list of dicts, convert to RentRollItem objects
            rent_roll = [RentRollItem(**item) for item in rent_roll_data]
        except (ValueError, IndexError, TypeError) as e:
            raise HTTPException(status_code=400, detail=f"Failed to extract valid Rent Roll: {e}")

        # 3. Extract Raw Expenses
        raw_expenses = self.ingest_financials_from_pdf(document_id)

        # 4. Normalize Expenses
        normalized_expenses = self.normalization_service.normalize_expenses(raw_expenses)

        # 5. Create UnderwritingAnalysis object
        analysis = UnderwritingAnalysis(
            document_id=document_id,
            pass_fail_status="PASS",
            property_meta=property_meta,
            rent_roll=rent_roll,
            rent_roll_summary=self._summarize_rent_roll(rent_roll),
            historical_expenses=normalized_expenses,
        )
        # 6. Compare Income Sources and Add Warning if Mismatch
        pnl_income = self.ingest_income_statement_from_pdf(document_id)
        rent_roll_income = analysis.rent_roll_summary.total_annual_rent
        
        income_discrepancy_warning = self.compare_income_sources(
            rent_roll_income, pnl_income
        )
        if income_discrepancy_warning:
            analysis.gating_reasons.append(income_discrepancy_warning)

        return analysis

    async def ingest_financials_from_pdf(self, document_id: str) -> List[Dict]:
        """
        Extracts raw T12 line items. We don't normalize yet, just get the text.
        Returns a list of dicts with 'description' and 'amount' keys.
        """
        raw_text = await self.ocr_backend_client.get_document_text(document_id)
        
        prompt = """
        Analyze this T12 Income Statement. Extract all EXPENSE line items.
        Ignore Income line items.
        Return a JSON array: [{"description": "Repair - Plumbing", "amount": 500.00}, ...]
        If the amount is in parentheses (500), treat it as a positive expense number.
        """
        
        raw_expenses = self.gemini_client.generate_structured_data(prompt=f"{prompt}\n\n{raw_text}", pdf_data=None)
        # Ensure we return a list
        return raw_expenses if isinstance(raw_expenses, list) else [raw_expenses]

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
        
        income_data_result = self.gemini_client.generate_structured_data(prompt=f"{prompt}\n\n{raw_text}", pdf_data=None)
        # generate_structured_data always returns a list, get first item
        if income_data_result and len(income_data_result) > 0:
            income_data = income_data_result[0]
        else:
            income_data = {}
        return float(income_data.get("total_annual_income", 0.0))

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