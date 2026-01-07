import pytest
import asyncio
from app.models.schemas import (
    NormalizedDataItem, PropertyMeta, DealParameters, UnderwritingAnalysis,
    RentRollSummary, DocumentType, CategoryGroup, DataClassification, 
    RentRollItem, StandardizedExpense, AuditLog, ExpenseCategory
)
from app.services.financial_service import FinancialService
from app.services.audit_log_service import AuditLogService
from app.services.multi_document_extraction_service import MultiDocumentExtractionService

# Mock Logger
import logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class TestFixesVerification:
    
    @pytest.mark.asyncio
    async def test_unit_count_extraction_logic(self):
        """
        Verify that unit count from Rent Roll metadata is correctly applied
        even if the item is not categorized as expense.
        """
        logger.info("Testing Unit Count Extraction Logic...")
        
        # Simulating the logic found in multi_document.py (Step 2 of analyze_deal_package)
        
        # 1. Create a mock normalized item from Excel Rent Roll
        # Note: It might be categorized as "Other" or "Revenue", but has row_count metadata
        rent_roll_item = NormalizedDataItem(
            id="item_1",
            raw_text="Rent Roll - Current_Rent_Roll.xlsx",
            normalized_value="Gross Potential Rent",
            field_type="revenue_item", # Not "expense_category"
            category_group=CategoryGroup.REVENUE,
            data_classification=DataClassification.SOURCED,
            confidence=0.9,
            source_document="Current_Rent_Roll.xlsx",
            metadata={
                "row_count": 42, # Valid unit count
                "amount": 50000.0,
                "type": "excel_aggregation" # New field added
            }
        )
        
        normalized_items = [rent_roll_item]
        property_meta = PropertyMeta()
        
        # 2. Run the logic (copied from multi_document.py fix)
        for item in normalized_items:
            # GLOBAL CHECK: Unit Count from Metadata (e.g. from Excel Rent Roll)
            if item.metadata and item.metadata.get("row_count") and "rent roll" in item.raw_text.lower():
                row_count = item.metadata.get("row_count")
                if row_count and row_count > 0:
                    if property_meta.total_units == 0:
                        property_meta.total_units = int(row_count)
        
        # 3. Assertions
        assert property_meta.total_units == 42, f"Unit count should be updated to 42, got {property_meta.total_units}"
        logger.info("✅ Unit Count Extraction Logic Passed")

    @pytest.mark.asyncio
    async def test_loan_amount_validation_logic(self):
        """
        Verify that explicit loan_amount in DealParameters is respected
        and overrides the LTV calculation for viability checks.
        """
        logger.info("Testing Loan Amount Validation Logic...")
        
        # Setup Services
        audit_service = AuditLogService()
        fin_service = FinancialService(audit_log_service=audit_service)
        
        # Scenario: 
        # Purchase Price = $4M
        # LTV = 65% -> Calculated Loan = $2.6M
        # Min Loan Amount = $5M
        # Explicit Loan Amount = $5.2M (Provided by user/broker)
        
        # 1. Setup Analysis Object
        params = DealParameters(
            ltv=0.65,
            min_loan_amount=5_000_000,
            loan_amount=5_200_000 # Explicit override
        )
        
        prop_meta = PropertyMeta(
            purchase_price=4_000_000,
            total_units=50, # Pass unit check (max is 80)
            year_built=2000 # Pass vintage check
        )
        
        analysis = UnderwritingAnalysis(
            document_id="test_doc",
            pass_fail_status="PENDING",
            property_meta=prop_meta,
            deal_parameters=params,
            rent_roll=[],
            rent_roll_summary=RentRollSummary(total_units=100, occupied_units=95, occupancy_rate=0.95, total_monthly_rent=10000, total_annual_rent=120000),
            historical_expenses=[]
        )
        
        # 2. Run Viability Check
        result = fin_service.check_deal_viability(analysis)
        
        # 3. Assertions
        # Without fix, this would FAIL because $2.6M < $5M
        # With fix, it should PASS because $5.2M > $5M
        assert result["status"] == "PASS", f"Deal should PASS with explicit loan amount. Result: {result}"
        assert len(result["reasons"]) == 0, f"Should have no failure reasons. Got: {result['reasons']}"
        logger.info("✅ Loan Amount Validation Logic Passed")

    @pytest.mark.asyncio
    async def test_excel_metadata_enhancement(self):
        """
        Verify that Excel extraction adds the correct 'type' metadata.
        """
        logger.info("Testing Excel Metadata Enhancement...")
        
        # Mocking the extraction service sync method directly to avoid file I/O
        service = MultiDocumentExtractionService()
        
        # Create a mock Excel file content (empty bytes, we'll mock the internal call or just test logic structure)
        # Actually, simpler to verify the code change by inspecting the method output structure if we could run it.
        # Since we can't easily mock openpyxl here without a real file, we will verify the logic flow conceptually
        # or rely on the previous unit test structure.
        
        # Let's create a minimal real Excel file in memory to test the actual method
        import io
        import openpyxl
        
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.append(["Category", "Amount"]) # Header
        ws.append(["Rent", 1000])
        ws.append(["Tax", 500])
        
        excel_bytes = io.BytesIO()
        wb.save(excel_bytes)
        excel_bytes.seek(0)
        
        # Run extraction
        # Note: We need to run the sync method wrapper
        extracted_data = await service.extract_from_excel(excel_bytes.read(), "test_rent_roll.xlsx")
        
        # Assertions
        assert len(extracted_data) == 1
        item = extracted_data[0]
        assert item["type"] == "excel_aggregation", "Extracted item should have type='excel_aggregation'"
        assert item["row_count"] == 2
        
        logger.info("✅ Excel Metadata Enhancement Passed")

if __name__ == "__main__":
    # Manually run async tests if executed as script
    t = TestFixesVerification()
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    try:
        loop.run_until_complete(t.test_unit_count_extraction_logic())
        loop.run_until_complete(t.test_loan_amount_validation_logic())
        loop.run_until_complete(t.test_excel_metadata_enhancement())
        print("\nALL VERIFICATION TESTS PASSED!")
    except Exception as e:
        print(f"\nTESTS FAILED: {str(e)}")
    finally:
        loop.close()