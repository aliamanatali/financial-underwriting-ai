"""
Tests for Tier B: Pipeline consolidation.

B1: ExpenseCategory → CategoryGroup mapping completeness
B2: Extraction-to-normalization adapter (input/output + pre-classification rules)
B3: NormSvc safety net rules
B4/B5: Feature flag wiring
"""

import pytest
from unittest.mock import MagicMock, AsyncMock, patch

from app.models.schemas import (
    ExpenseCategory, CategoryGroup, StandardizedExpense, AuditLog,
    NormalizedDataItem, DataClassification,
)
from app.services.category_group_mapping import CATEGORY_TO_GROUP, get_category_group
from app.services.multi_doc_normalization_adapter import (
    adapt_extraction_to_normalization,
    adapt_normalization_to_normalized_item,
)
from app.services.normalization_service import NormalizationService


@pytest.fixture
def norm_service():
    return NormalizationService(llm_service=MagicMock())


# ===========================================================================
# B1: Mapping completeness
# ===========================================================================

class TestCategoryGroupMapping:

    def test_every_expense_category_has_mapping(self):
        """Every ExpenseCategory enum value must have a CategoryGroup entry."""
        for category in ExpenseCategory:
            group = get_category_group(category)
            assert isinstance(group, CategoryGroup), (
                f"{category.name} mapped to {type(group)}, expected CategoryGroup"
            )

    def test_revenue_categories(self):
        assert get_category_group(ExpenseCategory.GROSS_POTENTIAL_RENT) == CategoryGroup.REVENUE
        assert get_category_group(ExpenseCategory.OTHER_INCOME) == CategoryGroup.REVENUE
        assert get_category_group(ExpenseCategory.REIMBURSEMENTS) == CategoryGroup.REVENUE

    def test_tax_insurance_categories(self):
        assert get_category_group(ExpenseCategory.REAL_ESTATE_TAXES) == CategoryGroup.TAX_INSURANCE
        assert get_category_group(ExpenseCategory.INSURANCE) == CategoryGroup.TAX_INSURANCE

    def test_opex_categories(self):
        assert get_category_group(ExpenseCategory.UTILITIES) == CategoryGroup.OPERATING_EXPENSE
        assert get_category_group(ExpenseCategory.MANAGEMENT_FEES) == CategoryGroup.OPERATING_EXPENSE
        assert get_category_group(ExpenseCategory.REPAIRS_MAINTENANCE) == CategoryGroup.OPERATING_EXPENSE

    def test_property_info_categories(self):
        assert get_category_group(ExpenseCategory.DEPOSIT) == CategoryGroup.PROPERTY_INFO
        assert get_category_group(ExpenseCategory.PURCHASE_PRICE) == CategoryGroup.PROPERTY_INFO
        assert get_category_group(ExpenseCategory.YEAR_BUILT) == CategoryGroup.PROPERTY_INFO

    def test_missing_category_raises_keyerror(self):
        """A category not in the mapping should raise KeyError with a clear message."""
        # We can't easily test this without removing an entry, but we can verify
        # the error message format by testing the function directly
        with pytest.raises(KeyError, match="has no entry in CATEGORY_TO_GROUP"):
            # Create a fake scenario by calling with a value not in the dict
            # We'll monkeypatch temporarily
            original = CATEGORY_TO_GROUP.copy()
            try:
                del CATEGORY_TO_GROUP[ExpenseCategory.UTILITIES]
                get_category_group(ExpenseCategory.UTILITIES)
            finally:
                CATEGORY_TO_GROUP.update(original)


# ===========================================================================
# B2: Adapter input → output
# ===========================================================================

class TestAdapterFieldMapping:

    def test_revenue_item_mapping(self):
        raw = [{"raw_text": "Monthly Rent", "amount": 2000, "type": "revenue", "subtype": "rent"}]
        result = adapt_extraction_to_normalization(raw)
        assert len(result) == 1
        assert result[0]["description"] == "Monthly Rent"
        assert result[0]["section_context"] == "income"

    def test_expense_item_mapping(self):
        raw = [{"raw_text": "Property Insurance", "amount": 12000, "type": "expense"}]
        result = adapt_extraction_to_normalization(raw)
        assert result[0]["description"] == "Property Insurance"
        assert result[0]["section_context"] == "expense"

    def test_capex_item_mapping(self):
        raw = [{"raw_text": "Roof Replacement", "amount": 50000, "type": "capex"}]
        result = adapt_extraction_to_normalization(raw)
        assert result[0]["section_context"] == "capex"

    def test_unknown_type_mapping(self):
        raw = [{"raw_text": "Something", "amount": 100, "type": "receivable"}]
        result = adapt_extraction_to_normalization(raw)
        assert result[0]["section_context"] == "unknown"

    def test_metadata_propagated(self):
        raw = [{
            "raw_text": "Tax", "amount": 5000, "type": "expense",
            "page_number": 3, "bbox": [10, 20, 30, 40],
            "source_document": "bill.pdf", "document_id": "abc",
            "expense_year": 2024, "amount_t3": 1200,
        }]
        result = adapt_extraction_to_normalization(raw)
        assert result[0]["page_number"] == 3
        assert result[0]["bbox"] == [10, 20, 30, 40]
        assert result[0]["source_document"] == "bill.pdf"
        assert result[0]["expense_year"] == 2024
        assert result[0]["amount_t3"] == 1200


# ===========================================================================
# B2: Adapter pre-classification rules
# ===========================================================================

class TestAdapterPreClassification:

    def test_past_due_revenue_becomes_receivable(self):
        raw = [{"raw_text": "Past due rent", "amount": 500, "type": "revenue"}]
        result = adapt_extraction_to_normalization(raw)
        assert result[0]["section_context"] == "unknown"  # receivable → unknown

    def test_capex_proposal_high_dollar(self):
        raw = [{"raw_text": "Roof replacement proposal", "amount": 50000, "type": "expense"}]
        result = adapt_extraction_to_normalization(raw)
        assert result[0]["section_context"] == "capex"

    def test_bare_permit_not_reclassified(self):
        raw = [{"raw_text": "Building permit", "amount": 200, "type": "expense"}]
        result = adapt_extraction_to_normalization(raw)
        assert result[0]["section_context"] == "expense"  # NOT capex

    def test_qualified_permit_reclassified(self):
        raw = [{"raw_text": "Building permit for renovation", "amount": 1500, "type": "expense"}]
        result = adapt_extraction_to_normalization(raw)
        assert result[0]["section_context"] == "capex"

    def test_deposit_becomes_property_info(self):
        raw = [{"raw_text": "Security deposit", "amount": 1000, "type": "expense"}]
        result = adapt_extraction_to_normalization(raw)
        assert result[0]["section_context"] == "unknown"  # property_info → unknown

    def test_student_blacklist(self):
        raw = [{"raw_text": "Tuition payment", "amount": 5000, "type": "expense"}]
        result = adapt_extraction_to_normalization(raw)
        assert result[0]["section_context"] == "unknown"  # other → unknown


# ===========================================================================
# B2: Total line suppression
# ===========================================================================

class TestAdapterTotalSuppression:

    def test_total_charges_dropped(self):
        raw = [
            {"raw_text": "Water service", "amount": 100, "type": "expense"},
            {"raw_text": "Total charges", "amount": 100, "type": "expense"},
        ]
        result = adapt_extraction_to_normalization(raw)
        assert len(result) == 1
        assert result[0]["description"] == "Water service"

    def test_total_amount_due_dropped(self):
        raw = [
            {"raw_text": "Electric", "amount": 200, "type": "expense"},
            {"raw_text": "Total amount due", "amount": 200, "type": "expense"},
        ]
        result = adapt_extraction_to_normalization(raw)
        assert len(result) == 1

    def test_non_expense_total_not_dropped(self):
        """'Total' in revenue context should NOT be dropped."""
        raw = [{"raw_text": "Total rental income", "amount": 5000, "type": "revenue"}]
        result = adapt_extraction_to_normalization(raw)
        assert len(result) == 1  # Only drops expense totals


# ===========================================================================
# B2: Back-adapter (StandardizedExpense → NormalizedDataItem)
# ===========================================================================

class TestBackAdapter:

    def test_tax_maps_to_tax_insurance_group(self):
        std = StandardizedExpense(
            original_text="Property Tax", mapped_category=ExpenseCategory.REAL_ESTATE_TAXES,
            amount=50000, confidence=0.95,
            audit_log=AuditLog(field_name="test", extracted_value=50000, source="T12", method="LLM"),
        )
        raw = {"raw_text": "Property Tax", "amount": 50000, "source_document": "tax_bill.pdf"}
        item = adapt_normalization_to_normalized_item(std, raw)
        assert item.category_group == CategoryGroup.TAX_INSURANCE
        assert item.normalized_value == "Real Estate Taxes"
        assert item.source_document == "tax_bill.pdf"

    def test_other_income_maps_to_revenue_group(self):
        std = StandardizedExpense(
            original_text="Parking", mapped_category=ExpenseCategory.OTHER_INCOME,
            amount=10800, confidence=1.0,
            audit_log=AuditLog(field_name="test", extracted_value=10800, source="OM", method="LLM"),
        )
        raw = {"raw_text": "Parking", "amount": 10800, "source_document": "om.pdf"}
        item = adapt_normalization_to_normalized_item(std, raw)
        assert item.category_group == CategoryGroup.REVENUE
        assert item.field_type == "revenue_item"

    def test_opex_maps_to_operating_expense(self):
        std = StandardizedExpense(
            original_text="Utilities", mapped_category=ExpenseCategory.UTILITIES,
            amount=11000, confidence=0.90,
            audit_log=AuditLog(field_name="test", extracted_value=11000, source="T12", method="LLM"),
        )
        raw = {"raw_text": "Utilities", "amount": 11000}
        item = adapt_normalization_to_normalized_item(std, raw)
        assert item.category_group == CategoryGroup.OPERATING_EXPENSE
        assert item.field_type == "expense_category"

    def test_metadata_populated(self):
        std = StandardizedExpense(
            original_text="Insurance", mapped_category=ExpenseCategory.INSURANCE,
            amount=9000, confidence=0.95,
            audit_log=AuditLog(field_name="test", extracted_value=9000, source="bill", method="test"),
        )
        raw = {"raw_text": "Insurance", "amount": 9000, "page_number": 2, "bbox": [1, 2, 3, 4], "expense_year": 2023}
        item = adapt_normalization_to_normalized_item(std, raw)
        assert item.metadata["page_number"] == 2
        assert item.metadata["bbox"] == [1, 2, 3, 4]
        assert item.metadata["expense_year"] == 2023


# ===========================================================================
# B3: Safety net rules in NormalizationService
# ===========================================================================

class TestSafetyNetRules:

    @pytest.mark.asyncio
    async def test_past_due_forced_to_accounts_receivable(self, norm_service):
        raw = [{"description": "Past due rent - outstanding balance", "amount": 1500}]

        async def mock_map(batch, categories):
            return [{"original_text": "Past due rent - outstanding balance",
                     "mapped_category": ExpenseCategory.OTHER_INCOME.value,
                     "confidence": 0.70, "reasoning": "Income"}]

        norm_service.llm_service.map_expenses_to_categories_async = mock_map
        with patch.object(norm_service, '_get_cached_mappings', new_callable=AsyncMock, return_value={}), \
             patch.object(norm_service, '_save_mappings', new_callable=AsyncMock):
            results = await norm_service.normalize_expenses_async(raw, document_id="test")

        assert len(results) == 1
        assert results[0].mapped_category == ExpenseCategory.ACCOUNTS_RECEIVABLE

    @pytest.mark.asyncio
    async def test_high_dollar_modernization_forced_to_capex(self, norm_service):
        raw = [{"description": "Elevator modernization", "amount": 25000}]

        async def mock_map(batch, categories):
            return [{"original_text": "Elevator modernization",
                     "mapped_category": ExpenseCategory.REPAIRS_MAINTENANCE.value,
                     "confidence": 0.75, "reasoning": "Repair"}]

        norm_service.llm_service.map_expenses_to_categories_async = mock_map
        with patch.object(norm_service, '_get_cached_mappings', new_callable=AsyncMock, return_value={}), \
             patch.object(norm_service, '_save_mappings', new_callable=AsyncMock):
            results = await norm_service.normalize_expenses_async(raw, document_id="test")

        assert len(results) == 1
        assert results[0].mapped_category == ExpenseCategory.CAPITAL_RESERVES

    @pytest.mark.asyncio
    async def test_low_dollar_modernization_not_forced(self, norm_service):
        """Amount below $5k threshold → LLM classification stands."""
        raw = [{"description": "Small modernization task", "amount": 500}]

        async def mock_map(batch, categories):
            return [{"original_text": "Small modernization task",
                     "mapped_category": ExpenseCategory.REPAIRS_MAINTENANCE.value,
                     "confidence": 0.80, "reasoning": "Repair"}]

        norm_service.llm_service.map_expenses_to_categories_async = mock_map
        with patch.object(norm_service, '_get_cached_mappings', new_callable=AsyncMock, return_value={}), \
             patch.object(norm_service, '_save_mappings', new_callable=AsyncMock):
            results = await norm_service.normalize_expenses_async(raw, document_id="test")

        assert len(results) == 1
        assert results[0].mapped_category == ExpenseCategory.REPAIRS_MAINTENANCE

    @pytest.mark.asyncio
    async def test_deposit_forced_to_deposit(self, norm_service):
        raw = [{"description": "Security deposit refund", "amount": 1000}]

        async def mock_map(batch, categories):
            return [{"original_text": "Security deposit refund",
                     "mapped_category": ExpenseCategory.OTHER_OPERATING_EXPENSES.value,
                     "confidence": 0.60, "reasoning": "Expense"}]

        norm_service.llm_service.map_expenses_to_categories_async = mock_map
        with patch.object(norm_service, '_get_cached_mappings', new_callable=AsyncMock, return_value={}), \
             patch.object(norm_service, '_save_mappings', new_callable=AsyncMock):
            results = await norm_service.normalize_expenses_async(raw, document_id="test")

        assert len(results) == 1
        assert results[0].mapped_category == ExpenseCategory.DEPOSIT


# ===========================================================================
# B5: Feature flag
# ===========================================================================

class TestFeatureFlag:

    def test_flag_removed(self):
        """After Tier C cutover, the feature flag is removed entirely."""
        from app.config import settings
        assert not hasattr(settings, 'use_consolidated_normalization')


# ===========================================================================
# C2: Batch sizing (BATCH_SIZE=100)
# ===========================================================================

class TestBatchSizing:

    @pytest.mark.asyncio
    async def test_small_deal_single_batch(self, norm_service):
        """15 items → 1 batch at BATCH_SIZE=100."""
        batches_seen = []

        async def mock_map(batch, categories):
            batches_seen.append(len(batch))
            return [{"original_text": item["description"],
                     "mapped_category": "Utilities", "confidence": 0.90, "reasoning": "test"}
                    for item in batch]

        norm_service.llm_service.map_expenses_to_categories_async = mock_map
        raw = [{"description": f"Item {i}", "amount": 100} for i in range(15)]
        with patch.object(norm_service, '_get_cached_mappings', new_callable=AsyncMock, return_value={}), \
             patch.object(norm_service, '_save_mappings', new_callable=AsyncMock):
            await norm_service.normalize_expenses_async(raw, document_id="test")

        assert len(batches_seen) == 1
        assert batches_seen[0] == 15

    @pytest.mark.asyncio
    async def test_150_items_two_batches(self, norm_service):
        """150 items → 2 batches (100 + 50)."""
        batches_seen = []

        async def mock_map(batch, categories):
            batches_seen.append(len(batch))
            return [{"original_text": item["description"],
                     "mapped_category": "Utilities", "confidence": 0.90, "reasoning": "test"}
                    for item in batch]

        norm_service.llm_service.map_expenses_to_categories_async = mock_map
        raw = [{"description": f"Item {i}", "amount": 100} for i in range(150)]
        with patch.object(norm_service, '_get_cached_mappings', new_callable=AsyncMock, return_value={}), \
             patch.object(norm_service, '_save_mappings', new_callable=AsyncMock):
            await norm_service.normalize_expenses_async(raw, document_id="test")

        assert len(batches_seen) == 2
        assert sorted(batches_seen) == [50, 100]

    @pytest.mark.asyncio
    async def test_550_items_six_batches(self, norm_service):
        """550 items → 6 batches (5×100 + 1×50)."""
        batches_seen = []

        async def mock_map(batch, categories):
            batches_seen.append(len(batch))
            return [{"original_text": item["description"],
                     "mapped_category": "Utilities", "confidence": 0.90, "reasoning": "test"}
                    for item in batch]

        norm_service.llm_service.map_expenses_to_categories_async = mock_map
        raw = [{"description": f"Item {i}", "amount": 100} for i in range(550)]
        with patch.object(norm_service, '_get_cached_mappings', new_callable=AsyncMock, return_value={}), \
             patch.object(norm_service, '_save_mappings', new_callable=AsyncMock):
            await norm_service.normalize_expenses_async(raw, document_id="test")

        assert len(batches_seen) == 6
