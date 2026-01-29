import logging
import json
from typing import Optional, List, Dict
from app.models.schemas import DocumentType
from app.services.gemini_service import GeminiService

logger = logging.getLogger(__name__)

class ClassificationService:
    """
    Service for classifying documents into standard DocumentTypes using Gemini.
    """
    
    def __init__(self, gemini_service: GeminiService):
        self.gemini_service = gemini_service

    async def classify_file(self, filename: str, content_preview: str = "") -> Optional[DocumentType]:
        """
        Classify a single file based on its filename and optional content preview.
        """
        try:
            # 1. Fast path: Check for obvious keywords in filename
            filename_lower = filename.lower()
            if "rent roll" in filename_lower:
                return DocumentType.RENT_ROLL
            if "t12" in filename_lower or "trailing 12" in filename_lower or "p&l" in filename_lower or "profit & loss" in filename_lower or "income statement" in filename_lower:
                return DocumentType.FINANCIALS
            if "om" in filename_lower or "offering memorandum" in filename_lower or "flyer" in filename_lower:
                return DocumentType.OFFERING_MEMORANDUM
            if "lease" in filename_lower and "agreement" in filename_lower:
                return DocumentType.LEASES
            if "tax" in filename_lower and "bill" in filename_lower:
                return DocumentType.TAX_BILLS
            
            # 2. LLM path: Use Gemini to infer from filename (and content if provided)
            prompt = f"""
            Classify the following document into one of these categories:
            
            Categories:
            - {DocumentType.OFFERING_MEMORANDUM.value}
            - {DocumentType.RENT_ROLL.value}
            - {DocumentType.LEASES.value}
            - {DocumentType.FINANCIALS.value} (includes T12, P&L, Income Statements, Balance Sheets)
            - {DocumentType.BUILDING_PLANS_PERMITS.value}
            - {DocumentType.DISCLOSURES.value}
            - {DocumentType.TAX_BILLS.value}
            - {DocumentType.UTILITIES.value}
            
            Filename: "{filename}"
            Content Preview: "{content_preview[:500] if content_preview else 'N/A'}"
            
            Return ONLY the exact category name from the list above. If you are unsure or it doesn't fit, return "Unknown".
            """
            
            response = await self.gemini_service.generate_content_async(prompt)
            result = response.strip().replace('"', '').replace("'", "")
            
            # Match result to enum
            for doc_type in DocumentType:
                if doc_type.value.lower() == result.lower():
                    return doc_type
            
            # Try partial matches if exact match fails
            if "financial" in result.lower():
                return DocumentType.FINANCIALS
            if "rent" in result.lower() and "roll" in result.lower():
                return DocumentType.RENT_ROLL
            if "offering" in result.lower() or "memorandum" in result.lower():
                return DocumentType.OFFERING_MEMORANDUM
            
            logger.info(f"LLM could not confidently classify '{filename}' (Result: {result}). Defaults to Unknown.")
            return None

        except Exception as e:
            logger.error(f"Error classifying file {filename}: {str(e)}")
            return None

    async def classify_files_batch(self, filenames: List[str]) -> Dict[str, DocumentType]:
        """
        Classify a batch of filenames using a single LLM call for efficiency.
        """
        if not filenames:
            return {}
            
        try:
            prompt = f"""
            You are a document classifier for a commercial real estate underwriting system.
            Classify each of the following filenames into exactly one of these categories:
            
            Categories:
            - {DocumentType.OFFERING_MEMORANDUM.value}
            - {DocumentType.RENT_ROLL.value}
            - {DocumentType.LEASES.value}
            - {DocumentType.FINANCIALS.value}
            - {DocumentType.BUILDING_PLANS_PERMITS.value}
            - {DocumentType.DISCLOSURES.value}
            - {DocumentType.TAX_BILLS.value}
            - {DocumentType.UTILITIES.value}
            - Unknown
            
            Filenames to classify:
            {json.dumps(filenames, indent=2)}
            
            Return a JSON object where keys are the filenames and values are the category names.
            Example:
            {{
                "prop_t12.xlsx": "{DocumentType.FINANCIALS.value}",
                "unknown_file.txt": "Unknown"
            }}
            """
            
            response = await self.gemini_service.generate_content_async(prompt)
            
            # Clean response
            cleaned_text = response.strip()
            if cleaned_text.startswith("```json"):
                cleaned_text = cleaned_text[7:]
            if cleaned_text.startswith("```"):
                cleaned_text = cleaned_text[3:]
            if cleaned_text.endswith("```"):
                cleaned_text = cleaned_text[:-3]
            
            results_dict = json.loads(cleaned_text.strip())
            
            # Map strings to Enums
            final_map = {}
            for fname, cat_str in results_dict.items():
                matched = False
                for doc_type in DocumentType:
                    if doc_type.value.lower() == cat_str.lower():
                        final_map[fname] = doc_type
                        matched = True
                        break
                
                # Fallback heuristics for common mismatches
                if not matched:
                    if "financial" in cat_str.lower():
                        final_map[fname] = DocumentType.FINANCIALS
                    elif "rent" in cat_str.lower():
                         final_map[fname] = DocumentType.RENT_ROLL
                    elif "lease" in cat_str.lower():
                         final_map[fname] = DocumentType.LEASES
                    elif "memo" in cat_str.lower():
                         final_map[fname] = DocumentType.OFFERING_MEMORANDUM
                    else:
                        # Keep it as None or map to a default?
                        # The caller handles missing keys or None
                        pass
                        
            return final_map
            
        except Exception as e:
            logger.error(f"Error in batch classification: {str(e)}")
            return {}