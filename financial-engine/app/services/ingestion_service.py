import pandas as pd
import json
from typing import List, Dict, Any
from extraction_pipeline.schemas import RentRollItem, PropertyMeta
from app.services.gemini_client import GeminiClient

class IngestionService:
    def __init__(self):
        self.gemini_client = GeminiClient()

    def ingest_rent_roll_from_excel(self, file_path: str, property_meta: PropertyMeta) -> List[RentRollItem]:
        """
        Ingests a rent roll from an Excel file.
        """
        df = pd.read_excel(file_path)
        
        # This is a simplified implementation. A real implementation would need to
        # dynamically find the header row and map columns to the RentRollItem schema.
        
        rent_roll = []
        for _, row in df.iterrows():
            rent_roll.append(RentRollItem(
                **row.to_dict()
            ))
            
        if len(rent_roll) != property_meta.total_units:
            raise ValueError(f"Unit count mismatch: {len(rent_roll)} in rent roll, {property_meta.total_units} in metadata")
            
        return rent_roll

    def ingest_rent_roll_from_pdf(self, file_path: str, property_meta: PropertyMeta) -> List[RentRollItem]:
        """
        Ingests a rent roll from a PDF file using an LLM-vision approach.
        """
        with open(file_path, "rb") as f:
            pdf_data = f.read()
            
        prompt = f"""
        Given the following PDF document, extract the rent roll information and return it as a JSON array of objects.
        Each object should match the following schema:
        {{
            "Unit #": "...",
            "Unit Type": "...",
            "Tenant Name": "...",
            "Current Rent": "...",
            "Market Rent": "...",
            "Lease Start": "...",
            "Lease End": "..."
        }}
        
        The total number of units should be {property_meta.total_units}.
        """
        
        # This is a conceptual implementation. The actual implementation would
        # need to send the PDF data to the Gemini API and parse the response.
        
        response = self.gemini_client.generate_content(prompt)
        rent_roll_data = json.loads(response)
        
        rent_roll = [RentRollItem(**item) for item in rent_roll_data]
        
        if len(rent_roll) != property_meta.total_units:
            raise ValueError(f"Unit count mismatch: {len(rent_roll)} in rent roll, {property_meta.total_units} in metadata")
        
        return rent_roll