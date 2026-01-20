import json
from typing import Dict
from typing import List
from app.services.gemini_client import GeminiClient
from app.models.schemas import PropertyMeta, OMProformaTable, OMProformaRow, OMTaxAssumptions

class OMScraperService:
    def __init__(self, gemini_client: GeminiClient = None):
        self.gemini_client = gemini_client or GeminiClient()

    def extract_proforma(self, raw_text: str) -> List[OMProformaTable]:
        """
        Extracts the 'Proforma' or 'Pro Forma' table from the OM text.
        This table usually contains columns like 'Current', 'Year 1', 'Pro Forma', etc.
        """
        prompt = """
        Analyze the Offering Memorandum text and find the "Proforma" or "Pro Forma" table(s).
        This table typically lists Income, Expenses, and NOI for different scenarios (e.g., "Current", "Year 1", "Market", "Stabilized").

        Task:
        1. Identify the Proforma tables.
        2. Extract each scenario (column) as a separate object.
        3. For each scenario, extract all rows (Income items, Expense items, NOI, etc.).
        
        The structure should be:
        [
            {
                "scenario_name": "Proforma at Stabilized Rent" (or "Year 1", "Current", etc.),
                "rows": [
                    {"row_name": "Gross Potential Market Rent", "annual": 1080000, "monthly": 90000, "per_unit": 33750, "percentage": null},
                    {"row_name": "Vacancy", "annual": -46191, "monthly": -3849, "per_unit": -1443, "percentage": 0.05},
                    ...
                    {"row_name": "Net Operating Income", "annual": 527577, "monthly": 43965, "per_unit": 16487, "percentage": null}
                ],
                "purchase_price": 9440000,
                "cap_rate": 0.0559,
                "grm": 10.22
            },
            ...
        ]

        CRITICAL RULES:
        - Extract "Annual", "Monthly", and "Per Unit" values if available.
        - Extract percentage values if available (e.g. 5.00% -> 0.05).
        - Preserve the EXACT row names as they appear in the document.
        - Maintain the order of rows as they appear in the table.
        - If multiple Proforma tables exist (e.g. "Current" vs "Market"), extract all of them.
        - Look for "Asking Price", "Purchase Price", "CAP Rate", "GRM" usually at the bottom of the proforma.

        Return ONLY the JSON array.
        """

        try:
            proforma_data = self.gemini_client.generate_structured_data(
                f"{prompt}\n\nDOCUMENT TEXT:\n{raw_text[:30000]}", # Limit text to avoid token limits if needed, but OM text can be large.
                expect_list=True,
                pydantic_schema=OMProformaTable
            )
            return [OMProformaTable(**item) if isinstance(item, dict) else item for item in proforma_data]
        except Exception as e:
            print(f"Error extracting OM Proforma: {e}")
            return []

    def extract_tax_assumptions(self, raw_text: str) -> OMTaxAssumptions:
        """
        Extracts specific tax assumptions from the OM text.
        """
        prompt = """
        Analyze the Offering Memorandum text and extract the following tax and fee assumptions:
        1. Tax Rate (as a decimal, e.g., 1.2% -> 0.012)
        2. Special Assessments (annual amount in dollars)
        3. Business Tax Rate (as a decimal, e.g., 2.88% -> 0.0288) - often applied to Gross Rent
        4. Rent Board Fee (amount per unit per year)

        Look for terms like "Ad Valorem", "Tax Rate", "Special Assessment", "Direct Charges", "Business Tax", "License Tax", "Rent Board", "Registration Fee".
        
        Return a JSON object with keys: "tax_rate", "special_assessments", "business_tax_rate", "rent_board_fee".
        If a value is not found, return null.
        """
        
        try:
            tax_data = self.gemini_client.generate_structured_data(
                f"{prompt}\n\nDOCUMENT TEXT SAMPLE:\n{raw_text[:30000]}",
                expect_list=False,
                pydantic_schema=OMTaxAssumptions
            )
            if isinstance(tax_data, dict):
                return OMTaxAssumptions(**tax_data)
            return OMTaxAssumptions()
        except Exception as e:
            print(f"Error extracting OM Tax Assumptions: {e}")
            return OMTaxAssumptions()

    def extract_om_details(self, file_path: str) -> PropertyMeta:
        """
        Extracts high-level deal info from the Offering Memorandum (OM).
        """
        # Legacy method stub
        return PropertyMeta(
            address="123 Main St",
            year_built=2022,
            purchase_price=0.0,
            total_units=32
        )

    def save_to_json(self, data: PropertyMeta, output_path: str):
        """
        Saves the extracted OM details to a JSON file.
        """
        with open(output_path, 'w') as f:
            json.dump(data.model_dump(), f, indent=4)