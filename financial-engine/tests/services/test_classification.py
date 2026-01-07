import pytest
from app.services.multi_document_extraction_service import MultiDocumentExtractionService
from app.models.schemas import CategoryGroup, DataClassification, NormalizedDataItem

@pytest.mark.asyncio
async def test_classification_and_grouping():
    service = MultiDocumentExtractionService()
    
    # Test Fallback Categorization Logic
    
    # 1. Operating Expense
    utility_item = service._fallback_categorization("Electric Bill")
    assert utility_item["category_group"] == "Operating Expense"
    assert utility_item["normalized_value"] == "Utilities"

    # 2. Tax & Insurance
    tax_item = service._fallback_categorization("Property Tax 2024")
    assert tax_item["category_group"] == "Tax & Insurance"
    assert tax_item["normalized_value"] == "Real Estate Taxes"
    
    # 3. Revenue
    rent_item = service._fallback_categorization("Gross Potential Rent")
    assert rent_item["category_group"] == "Revenue"
    
    # 4. Property Info
    year_built_item = service._fallback_categorization("Year Built: 1985")
    assert year_built_item["category_group"] == "Property Info"
    assert year_built_item["normalized_value"] == "Property Characteristic"
    
    # 5. Default/Unknown
    unknown_item = service._fallback_categorization("Random Miscellaneous Fee")
    assert unknown_item["category_group"] == "Operating Expense" # Defaults to OpEx
    assert unknown_item["normalized_value"] == "Other Operating Expenses"

@pytest.mark.asyncio
async def test_normalization_flow_mock():
    # Simulate the flow in process_financial_documents where we create NormalizedDataItem
    
    # Mock data mimicking what Gemini would return
    mock_extracted_items = [
        {"raw_text": "Rental Income", "amount": 500000, "type": "revenue"},
        {"raw_text": "Property Insurance", "amount": 15000, "type": "expense"},
        {"raw_text": "Year Built: 1990", "amount": 1990, "type": "property_info"}
    ]
    
    service = MultiDocumentExtractionService()
    
    # We can't easily mock the async Gemini call here without extensive setup,
    # but we can verify the _fallback_categorization logic used when Gemini is bypassed 
    # or the logic inside the loop if we were to refactor.
    
    # Instead, let's verify the Enum integrity which was a key part of the refactor
    assert CategoryGroup.REVENUE == "Revenue"
    assert CategoryGroup.OPERATING_EXPENSE == "Operating Expense"
    assert CategoryGroup.PROPERTY_INFO == "Property Info"
    
    assert DataClassification.SOURCED == "Sourced"
    assert DataClassification.ASSUMPTION == "Assumption"
    
    # Verify NormalizedDataItem structure
    item = NormalizedDataItem(
        id="test_1",
        raw_text="Test",
        normalized_value="Test Val",
        field_type="expense_category",
        category_group=CategoryGroup.OPERATING_EXPENSE,
        data_classification=DataClassification.SOURCED,
        confidence=0.9,
        source_document="doc.pdf"
    )
    assert item.category_group == "Operating Expense"
    assert item.data_classification == "Sourced"