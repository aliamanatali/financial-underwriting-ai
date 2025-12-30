import json
from app.services.ingestion_service import IngestionService
from app.services.extract_om_details import OMScraperService
from app.services.normalization_service import NormalizationService
from app.services.gemini_client import GeminiClient

def main():
    # Initialize services
    ingestion_service = IngestionService()
    om_scraper_service = OMScraperService()
    gemini_client = GeminiClient()
    normalization_service = NormalizationService(gemini_client)

    # Assume the OCR service has already run and produced the raw JSON files
    # In a real pipeline, this script would be triggered after the OCR is complete
    
    # 1. Load the raw data from the OCR service (conceptual)
    # with open("rent_roll_raw.json", 'r') as f:
    #     rent_roll_raw = json.load(f)
        
    # with open("t12_expenses_raw.json", 'r') as f:
    #     t12_expenses_raw = json.load(f)
        
    # with open("om_details_raw.json", 'r') as f:
    #     om_details_raw = json.load(f)
        
    # 2. Process and normalize the data
    # property_meta = om_scraper_service.extract_om_details("path/to/om.pdf")
    # rent_roll = ingestion_service.ingest_rent_roll_from_excel("path/to/rent_roll.xlsx", property_meta)
    # normalized_expenses = normalization_service.normalize_expenses(t12_expenses_raw)
    
    # 3. Combine into a single deal_data.json
    # deal_data = {
    #     "property_meta": property_meta.model_dump(),
    #     "rent_roll": [item.model_dump() for item in rent_roll],
    #     "operating_expenses": [item.model_dump() for item in normalized_expenses]
    # }
    
    # with open("deal_data.json", 'w') as f:
    #     json.dump(deal_data, f, indent=4)
        
    print("deal_data.json created successfully (conceptual)")

if __name__ == '__main__':
    main()