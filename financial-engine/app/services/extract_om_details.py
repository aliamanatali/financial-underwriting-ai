import json
import logging
from typing import Dict, List, Any, Optional
from app.services.gemini_client import GeminiClient
from app.models.schemas import PropertyMeta, OMProformaTable, OMProformaRow, OMTaxAssumptions, RentRollItem, UnitTypeSummary

logger = logging.getLogger(__name__)

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
        4. CRITICAL: Be extremely thorough in finding all Operating Expenses (e.g., Real Estate Taxes, Insurance, Repairs & Maintenance, Utilities, Management Fees, Payroll, General & Administrative, Contract Services, Advertising, etc.).
        
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

        FILTERING RULES:
        - EXCLUDE "Rent Comparables" or "Sales Comparables" tables.
        - EXCLUDE data belonging to other properties (e.g. in a portfolio, only extract the subject property).
        - Ensure the extracted financials correspond to the Subject Property identified in the OM.

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

    async def extract_om_proforma_from_file(self, file_bytes: bytes, file_name: str, mime_type: str = "application/pdf") -> List[OMProformaTable]:
        """
        Async version of extract_proforma that uses file content directly with Gemini Vision.
        Supports PDF and Images.
        """
        file_type_desc = "Offering Memorandum PDF" if mime_type == "application/pdf" else "Offering Memorandum Image"
        
        prompt = f"""
        Analyze this {file_type_desc} and extract the "Proforma" or "Pro Forma" table(s).
        This table typically lists Income, Expenses, and NOI for different scenarios (e.g., "Current", "Year 1", "Market", "Stabilized").

        Task:
        1. Identify the Proforma tables.
        2. Extract each scenario (column) as a separate object.
        3. For each scenario, extract all rows (Income items, Expense items, NOI, etc.).
        4. CRITICAL: Be extremely thorough in finding all Operating Expenses. Common categories include: Taxes, Insurance, Utilities, Repairs/Maintenance, Management, Payroll, Marketing, etc.
        
        The structure should be:
        [
            {
                "scenario_name": "Proforma at Stabilized Rent",
                "rows": [
                    {"row_name": "Gross Potential Market Rent", "annual": 1080000, "monthly": 90000, "per_unit": 33750, "percentage": null, "page_number": 1, "bbox": [100, 100, 200, 200]},
                    ...
                ],
                "purchase_price": 9440000,
                "cap_rate": 0.0559,
                "grm": 10.22
            }
        ]

        CRITICAL RULES:
        - Extract "Annual", "Monthly", and "Per Unit" values.
        - Preserve the EXACT row names.
        - You MUST include 'page_number' (1-based integer) and 'bbox' ([ymin, xmin, ymax, xmax] 0-1000) for EVERY row to track its exact location. Do not omit them.
        - Extract all rows found in the table.
        - Look for "Asking Price", "Purchase Price", "CAP Rate", "GRM" usually at the bottom.

        FILTERING RULES:
        - EXCLUDE "Rent Comparables", "Sale Comparables", or "Comps" tables.
        - Ensure data belongs to the SUBJECT PROPERTY only.

        Return ONLY the JSON array.
        """
        
        try:
            # Check if client has async method and use FAST model for extraction if possible
            # Proforma extraction is complex, so we might want PRO, but let's try FAST first if available
            # Actually, for tables, PRO is much better. Let's default to standard model (Pro) for this task.
            if hasattr(self.gemini_client, 'generate_structured_data_async'):
                proforma_data = await self.gemini_client.generate_structured_data_async(
                    prompt,
                    pdf_data=file_bytes,
                    expect_list=True,
                    pydantic_schema=OMProformaTable,
                    mime_type=mime_type
                )
                return [OMProformaTable(**item) if isinstance(item, dict) else item for item in proforma_data]
            else:
                return []
                
        except Exception as e:
            print(f"Error extracting OM Proforma from file: {e}")
            return []

    async def extract_om_key_data(self, file_bytes: bytes, file_name: str, mime_type: str = "application/pdf") -> Dict[str, Any]:
        """
        Extracts key data from OM: Property Meta (Price, Units, Address) and Rent Roll.
        """
        file_type_desc = "Offering Memorandum PDF" if mime_type == "application/pdf" else "Offering Memorandum Image"

        prompt = f"""
        Analyze this {file_type_desc} and extract the following key information:
        
        1. Property Details:
           - LOOK FOR "PROPERTY OVERVIEW", "EXECUTIVE SUMMARY", or "INVESTMENT HIGHLIGHTS" tables/sections first.
           - Property Name: The explicit name of the SUBJECT PROPERTY (e.g., "The Oakwood Apartments").
             * Check for rows labeled "Property Name", "Name", or title headers in the Property Overview.
             * CRITICAL: Do NOT pick names of Comparable Properties ("Rent Comps", "Sales Comps") or the Brokerage Firm.
             * If the property has no specific name, use the Street Address (e.g., "123 Main Street Apartments").
           - Property Address: The full legal address (e.g. "2419 Durant Ave, Berkeley, CA 94704").
             * Check for rows labeled "Legal Address", "Property Address", "Location", or "Address".
           - Purchase Price / Asking Price
             * CRITICAL: Do NOT confuse with "Earnest Money Deposit", "Initial Deposit", or "Escrow Deposit".
             * Deposits are usually smaller amounts (e.g. $50k-$200k). Purchase Price is the full value.
           - Total Units (Unit Count)
           - Year Built
           - Rentable Sq Ft (NRA)
           
        2. Rent Roll Data:
           - YOUR PRIMARY GOAL is to find the DETAILED RENT ROLL table where every row corresponds to a SINGLE specific unit.
           - Look for a table with a column labeled "Unit", "Unit #", "Apt", "#", or "Suite".
           - IGNORE the "Unit Mix" or "Floor Plan Summary" table which groups units by type (e.g. "Studios", "1 Bedroom"). That is a summary, not the rent roll.
           - If you see a table listing Unit numbers like "101", "102", "A", "B" - EXTRACT THAT.
           
           For each row in the DETAILED Rent Roll:
             - unit_number: The specific identifier (e.g. "101"). REQUIRED.
             - unit_type: Extract the EXACT text from the document (e.g. "Studio", "1 Bed"). Do not normalize to "1BD/1BA" unless that is what is written.
             - is_vacant: (boolean) Set to true if the unit is vacant, false otherwise.
             - current_rent: Actual monthly rent. If VACANT, this might be 0 or empty.
             - market_rent: Market/Pro Forma monthly rent. Look for "Market", "Pro Forma", "Street Rent", "Potential Rent".
             - stabilized_rent: Stabilized/Post-Renovation monthly rent. Look for "Stabilized", "Year 2", "Post-Reno".
             - unit_size: Sq Ft.
             - lease_start: Lease start date (e.g., "01/01/2023").
             - lease_end: Lease expiration date (e.g., "12/31/2024").
             - move_in_date: Date tenant moved in (if available).
             - count: MUST BE 1 for detailed rows.
             
           VACANCY HANDLING:
           - Check "Status", "Tenant Name", or "Notes" columns for "Vacant", "VAC", "Model", "Empty".
           - If a unit is VACANT, set "is_vacant" to true.

           ONLY if a detailed rent roll is completely missing from the document, fallback to the Unit Mix summary.
        
        Return the data as a JSON object with this structure:
        {{
            "property_meta": {{
                "property_name": "The Oakwood Apartments",
                "purchase_price": 5000000,
                "total_units": 20,
                "address": "123 Main St, City, State",
                "year_built": 1980,
                "rentable_sqft": 15000,
                "page_number": 1,
                "bbox": [100, 100, 200, 200]
            }},
            "rent_roll_items": [
                {{
                    "unit_number": "101",
                    "unit_type": "1BD/1BA",
                    "is_vacant": false,
                    "count": 1,
                    "current_rent": 1500,
                    "market_rent": 1800,
                    "stabilized_rent": 1950,
                    "unit_size": 750,
                    "lease_start": "2023-01-01",
                    "lease_end": "2024-01-01",
                    "move_in_date": "2022-05-15",
                    "page_number": 1,
                    "bbox": [100, 100, 200, 200]
                }}
            ]
        }}
        
        CRITICAL INSTRUCTIONS:
        1. DO NOT extract the Unit Mix Summary if a Detailed Rent Roll exists.
        2. DO NOT hallucinate unit numbers.
        3. If the document spans multiple pages, extract data from ALL pages of the rent roll.
        4. "count" should be 1 if "unit_number" is present.
        5. You MUST include 'page_number' and 'bbox' (bounding box coordinates [ymin, xmin, ymax, xmax] 0-1000) for property_meta and EVERY rent_roll_item to track their exact location. Do not omit them.
        """
        
        try:
             if hasattr(self.gemini_client, 'generate_content_async'):
                # We use generate_content_async directly to get JSON
                from google.genai import types
                
                parts = [
                    types.Part.from_bytes(data=file_bytes, mime_type=mime_type),
                    types.Part.from_text(text=prompt)
                ]
                
                response = await self.gemini_client.client.aio.models.generate_content(
                    model=self.gemini_client.model_name,
                    contents=parts,
                    config=types.GenerateContentConfig(
                        temperature=0.0,
                        response_mime_type="application/json"
                    )
                )
                
                if response.text:
                    # Use GeminiClient's cleaning method for robustness
                    cleaned_text = self.gemini_client._clean_json_string(response.text)
                    return json.loads(cleaned_text)
                return {}
             else:
                 logger.warning("Gemini Client does not support async generation")
                 return {}

        except Exception as e:
            logger.error(f"Error extracting OM Key Data: {e}")
            return {}

    def extract_om_details(self, file_path: str) -> PropertyMeta:
        """
        Extracts high-level deal info from the Offering Memorandum (OM).
        """
        # Legacy method stub
        return PropertyMeta(
            property_name="Example Property",
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