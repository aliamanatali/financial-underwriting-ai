import asyncio
import logging
import unittest
from app.services.normalization_service import NormalizationService
from app.services.multi_document_extraction_service import MultiDocumentExtractionService
from app.models.schemas import RentRollItem, StandardizedExpense, ExpenseCategory

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class MockLLMService:
    async def map_expenses_to_categories_async(self, expenses, categories):
        return []

class TestFixes(unittest.IsolatedAsyncioTestCase):
    
    async def test_unit_mix_parking_exclusion(self):
        logger.info("Testing Unit Mix - Parking Exclusion...")
        norm_service = NormalizationService(llm_service=MockLLMService())
        
        raw_rent_roll = [
            {"unit_number": "1", "unit_type": "1BR", "tenant_name": "Tenant A", "current_rent": 1000},
            {"unit_number": "6", "unit_type": "Parking", "tenant_name": "Blue Honda Accord", "current_rent": 120},
            {"unit_number": "8", "unit_type": "Storage", "tenant_name": "Tan Honda Civic", "current_rent": 150},
            {"unit_number": "101", "unit_type": "2BR", "tenant_name": "Tenant B", "current_rent": 2000}
        ]
        
        normalized = norm_service.normalize_rent_roll(raw_rent_roll)
        
        # Should only have 2 items (Unit 1 and 101)
        self.assertEqual(len(normalized), 2)
        self.assertEqual(normalized[0].unit_number, "1")
        self.assertEqual(normalized[1].unit_number, "101")
        logger.info("Unit Mix test passed.")

    async def test_stabilized_rent_fix(self):
        logger.info("Testing Stabilized Rent Fix...")
        norm_service = NormalizationService(llm_service=MockLLMService())
        
        raw_rent_roll = [
            {"unit_number": "1", "unit_type": "1BR", "tenant_name": "Tenant A", "current_rent": 1500, "stabilized_rent": 0},
            {"unit_number": "2", "unit_type": "1BR", "tenant_name": "Tenant B", "current_rent": 1600, "stabilized_rent": 1800},
            {"unit_number": "3", "unit_type": "1BR", "tenant_name": "Vacant", "current_rent": 0, "stabilized_rent": 0} 
        ]
        
        normalized = norm_service.normalize_rent_roll(raw_rent_roll)
        
        # Unit 1: Stabilized should be 1500 (defaulted to current)
        self.assertEqual(normalized[0].stabilized_rent, 1500.0)
        
        # Unit 2: Stabilized should remain 1800
        self.assertEqual(normalized[1].stabilized_rent, 1800.0)
        
        # Unit 3: Stabilized should remain 0 (since current is 0)
        self.assertEqual(normalized[2].stabilized_rent, 0.0)
        logger.info("Stabilized Rent test passed.")

    async def test_expense_aggregation_exclusion(self):
        logger.info("Testing Expense Aggregation Exclusion...")
        norm_service = NormalizationService(llm_service=MockLLMService())
        
        # Mock cached mappings to avoid LLM/Cache calls, or ensure fallbacks are used.
        # normalize_expenses_async checks cache, then LLM.
        # We can bypass this by mocking _get_cached_mappings to return nothing, 
        # and MockLLMService returns nothing.
        # Then it relies on fallback mapping logic, BUT the exclusion happens in the final loop over raw_expenses.
        
        raw_expenses = [
            {"description": "Landscaping", "amount": 1000},
            {"description": "Principal Balance", "amount": 4900000},
            {"description": "Loan Amount", "amount": 5000000},
            {"description": "Profit & Loss Summary", "amount": 64000000},
            {"description": "Repairs", "amount": 500}
        ]
        
        # Mock _get_cached_mappings to avoid DB calls
        async def mock_get_cached(x): return {}
        norm_service._get_cached_mappings = mock_get_cached
        
        # Mock _save_mappings
        async def mock_save_mappings(x): return None
        norm_service._save_mappings = mock_save_mappings
        
        normalized = await norm_service.normalize_expenses_async(raw_expenses)
        
        descriptions = [item.original_text for item in normalized]
        
        self.assertIn("Landscaping", descriptions)
        self.assertIn("Repairs", descriptions)
        self.assertNotIn("Principal Balance", descriptions)
        self.assertNotIn("Loan Amount", descriptions)
        self.assertNotIn("Profit & Loss Summary", descriptions)
        logger.info("Expense Aggregation test passed.")

    async def test_capex_identification(self):
        logger.info("Testing CapEx Identification...")
        extract_service = MultiDocumentExtractionService()
        
        raw_expenses = [
            {"raw_text": "Elevator Modernization", "type": "expense", "amount": 50000},
            {"raw_text": "Retaining Wall Repair", "type": "expense", "amount": 19000},
            {"raw_text": "Proposal for HVAC", "type": "expense", "amount": 20000},
            {"raw_text": "Small Repair", "type": "expense", "amount": 100},
            {"raw_text": "Cylinder Replacement", "type": "expense", "amount": 158000}
        ]
        
        fixed = extract_service._validate_and_fix_extraction(raw_expenses)
        
        for item in fixed:
            text = item["raw_text"]
            type_val = item["type"]
            
            if "Elevator" in text:
                self.assertEqual(type_val, "capex")
            elif "Retaining Wall" in text:
                self.assertEqual(type_val, "capex")
            elif "Proposal" in text:
                self.assertEqual(type_val, "capex")
            elif "Cylinder" in text:
                self.assertEqual(type_val, "capex")
            elif "Small Repair" in text:
                self.assertEqual(type_val, "expense")
                
        logger.info("CapEx Identification test passed.")

if __name__ == '__main__':
    unittest.main()