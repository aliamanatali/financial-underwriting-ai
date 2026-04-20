"""
Tests for Tier 1 extraction pipeline fixes.

1.1 Batch scoping: multi-batch normalization correctly links amounts
1.2 Unit 6/8 logic removed: units 6 and 8 are processed normally
1.3 Insurance reclassification: per-unit scaling replaces flat $25k threshold
1.4 OM Primacy: category-coverage rule replaces arbitrary count > 5
"""

import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from app.services.normalization_service import NormalizationService
from app.services.financial_service import FinancialService
from app.models.schemas import (
    ExpenseCategory, StandardizedExpense, AuditLog,
)
from app.services.audit_log_service import AuditLogService


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def norm_service():
    """NormalizationService with a mock LLM that echoes descriptions as categories."""
    mock_llm = MagicMock()
    return NormalizationService(llm_service=mock_llm)


@pytest.fixture
def fin_service():
    return FinancialService(audit_log_service=MagicMock(spec=AuditLogService))


def _make_expense(text, amount, category=ExpenseCategory.OTHER_OPERATING_EXPENSES,
                  source_document=None, user_verified=False, expense_year=None):
    """Helper to build a StandardizedExpense for dedup tests."""
    return StandardizedExpense(
        original_text=text,
        mapped_category=category,
        amount=amount,
        confidence=0.90,
        audit_log=AuditLog(
            field_name=f"Expense: {category.value}",
            extracted_value=amount,
            source=source_document or "T12",
            method="test",
        ),
        source_document=source_document,
        user_verified=user_verified,
        expense_year=expense_year,
    )


# ===========================================================================
# 1.1  Batch scoping bug — batches[i] instead of stale `batch` closure var
# ===========================================================================

class TestBatchScoping:
    """
    The batch scoping bug caused items in later batches to fail the
    original_match lookup (searching the wrong batch), losing
    amounts/metadata.  After the fix every item should retain
    its original amount regardless of how many batches are used.
    """

    @pytest.mark.asyncio
    async def test_multi_batch_preserves_amounts(self, norm_service):
        """Multiple items across batches. Every item keeps its original amount."""
        # Build 30 unique expenses with known amounts
        raw_expenses = [
            {"description": f"Expense Item {i}", "amount": 1000 + i, "page_number": i}
            for i in range(30)
        ]

        # Mock the LLM to echo descriptions back as "Other Operating Expenses"
        async def mock_map(batch, categories):
            return [
                {
                    "original_text": item["description"],
                    "mapped_category": ExpenseCategory.OTHER_OPERATING_EXPENSES.value,
                    "confidence": 0.90,
                    "reasoning": "test",
                }
                for item in batch
            ]

        norm_service.llm_service.map_expenses_to_categories_async = mock_map

        # Stub cache to return empty (force LLM path)
        with patch.object(norm_service, '_get_cached_mappings', new_callable=AsyncMock, return_value={}), \
             patch.object(norm_service, '_save_mappings', new_callable=AsyncMock):
            results = await norm_service.normalize_expenses_async(raw_expenses, document_id="test")

        assert len(results) == 30

        # Every result should have its correct original amount
        result_by_text = {r.original_text: r for r in results}
        for i in range(30):
            desc = f"Expense Item {i}"
            assert desc in result_by_text, f"Missing: {desc}"
            assert result_by_text[desc].amount == 1000 + i, (
                f"{desc}: expected {1000 + i}, got {result_by_text[desc].amount}"
            )

    @pytest.mark.asyncio
    async def test_multi_batch_preserves_page_numbers(self, norm_service):
        """Page numbers from the original raw expense survive the batch merge."""
        raw_expenses = [
            {"description": f"Item {i}", "amount": 500 + i, "page_number": i + 10}
            for i in range(30)
        ]

        async def mock_map(batch, categories):
            return [
                {
                    "original_text": item["description"],
                    "mapped_category": ExpenseCategory.UTILITIES.value,
                    "confidence": 0.88,
                    "reasoning": "test",
                }
                for item in batch
            ]

        norm_service.llm_service.map_expenses_to_categories_async = mock_map

        with patch.object(norm_service, '_get_cached_mappings', new_callable=AsyncMock, return_value={}), \
             patch.object(norm_service, '_save_mappings', new_callable=AsyncMock):
            results = await norm_service.normalize_expenses_async(raw_expenses, document_id="test")

        # Verify page_number was propagated through audit_log
        for i, r in enumerate(results):
            assert r.audit_log.page_number == i + 10, (
                f"Item {i}: expected page {i + 10}, got {r.audit_log.page_number}"
            )


# ===========================================================================
# 1.2  Unit 6/8 hardcoded logic removed
# ===========================================================================

class TestUnit68Removed:
    """Units numbered 6 and 8 must be processed normally — no forced $0 rent."""

    def test_unit_6_keeps_rent(self, norm_service):
        raw_items = [
            {
                "unit_number": "6",
                "unit_type": "1BR",
                "tenant_name": "John Smith",
                "current_rent": 1500,
                "market_rent": 1800,
                "lease_start": "2025-01-01",
                "lease_end": "2026-01-01",
            }
        ]
        result = norm_service.normalize_rent_roll(raw_items)
        assert len(result) == 1
        assert result[0].current_rent == 1500
        assert result[0].tenant_name == "John Smith"
        assert result[0].lease_start == "2025-01-01"

    def test_unit_8_keeps_rent(self, norm_service):
        raw_items = [
            {
                "unit_number": "8",
                "unit_type": "2BR",
                "tenant_name": "Jane Doe",
                "current_rent": 2200,
                "market_rent": 2400,
                "lease_start": "2025-06-01",
                "lease_end": "2026-06-01",
            }
        ]
        result = norm_service.normalize_rent_roll(raw_items)
        assert len(result) == 1
        assert result[0].current_rent == 2200
        assert result[0].tenant_name == "Jane Doe"

    def test_vacant_unit_6_stays_vacant(self, norm_service):
        """A legitimately vacant unit 6 should stay vacant, not get 'Returning Tenant'."""
        raw_items = [
            {
                "unit_number": "6",
                "unit_type": "1BR",
                "tenant_name": "Vacant",
                "current_rent": 0,
                "market_rent": 1500,
            }
        ]
        result = norm_service.normalize_rent_roll(raw_items)
        assert len(result) == 1
        assert result[0].is_vacant is True
        # Must NOT have been renamed to "Returning Tenant (Possession)"
        assert "Returning Tenant" not in (result[0].tenant_name or "")


# ===========================================================================
# 1.3  Insurance reclassification — per-unit scaling
# ===========================================================================

class TestInsuranceReclassification:
    """
    Old behavior: any Insurance > $25k → Capital Reserves.
    New behavior: per-unit scaling ($1,500/unit ceiling), keyword-based reclassification.
    """

    @pytest.mark.asyncio
    async def test_9unit_25k_insurance_kept(self, norm_service):
        """9-unit property, $25k insurance (~$2,778/unit) → keep as Insurance but lower confidence."""
        raw = [{"description": "Property Insurance Premium", "amount": 25000}]

        async def mock_map(batch, categories):
            return [{
                "original_text": "Property Insurance Premium",
                "mapped_category": ExpenseCategory.INSURANCE.value,
                "confidence": 0.92,
                "reasoning": "Standard insurance premium",
            }]

        norm_service.llm_service.map_expenses_to_categories_async = mock_map
        with patch.object(norm_service, '_get_cached_mappings', new_callable=AsyncMock, return_value={}), \
             patch.object(norm_service, '_save_mappings', new_callable=AsyncMock):
            results = await norm_service.normalize_expenses_async(raw, document_id="test", total_units=9)

        assert len(results) == 1
        assert results[0].mapped_category == ExpenseCategory.INSURANCE
        # Per-unit = $2,778 > $1,500 ceiling → confidence lowered to 0.70
        assert results[0].confidence <= 0.70

    @pytest.mark.asyncio
    async def test_32unit_40k_insurance_kept(self, norm_service):
        """32-unit property, $40k insurance (~$1,250/unit) → keep as Insurance, normal confidence."""
        raw = [{"description": "Annual Insurance", "amount": 40000}]

        async def mock_map(batch, categories):
            return [{
                "original_text": "Annual Insurance",
                "mapped_category": ExpenseCategory.INSURANCE.value,
                "confidence": 0.93,
                "reasoning": "Annual premium",
            }]

        norm_service.llm_service.map_expenses_to_categories_async = mock_map
        with patch.object(norm_service, '_get_cached_mappings', new_callable=AsyncMock, return_value={}), \
             patch.object(norm_service, '_save_mappings', new_callable=AsyncMock):
            results = await norm_service.normalize_expenses_async(raw, document_id="test", total_units=32)

        assert len(results) == 1
        assert results[0].mapped_category == ExpenseCategory.INSURANCE
        # Per-unit = $1,250 < $1,500 ceiling → confidence unchanged
        assert results[0].confidence == 0.93

    @pytest.mark.asyncio
    async def test_9unit_75k_insurance_reserve_reclassified(self, norm_service):
        """9-unit, $75k 'insurance reserve for roof' → reclassify to Capital Reserves (CapEx keyword)."""
        raw = [{"description": "Insurance Reserve for Roof Replacement", "amount": 75000}]

        async def mock_map(batch, categories):
            return [{
                "original_text": "Insurance Reserve for Roof Replacement",
                "mapped_category": ExpenseCategory.INSURANCE.value,
                "confidence": 0.80,
                "reasoning": "Insurance related",
            }]

        norm_service.llm_service.map_expenses_to_categories_async = mock_map
        with patch.object(norm_service, '_get_cached_mappings', new_callable=AsyncMock, return_value={}), \
             patch.object(norm_service, '_save_mappings', new_callable=AsyncMock):
            results = await norm_service.normalize_expenses_async(raw, document_id="test", total_units=9)

        assert len(results) == 1
        # "reserve" is a CapEx keyword → reclassified
        assert results[0].mapped_category == ExpenseCategory.CAPITAL_RESERVES

    @pytest.mark.asyncio
    async def test_insurance_limit_keyword_reclassified(self, norm_service):
        """Item with 'coverage' keyword → always reclassified regardless of amount or units."""
        raw = [{"description": "General Liability Coverage", "amount": 5000}]

        async def mock_map(batch, categories):
            return [{
                "original_text": "General Liability Coverage",
                "mapped_category": ExpenseCategory.INSURANCE.value,
                "confidence": 0.85,
                "reasoning": "Insurance",
            }]

        norm_service.llm_service.map_expenses_to_categories_async = mock_map
        with patch.object(norm_service, '_get_cached_mappings', new_callable=AsyncMock, return_value={}), \
             patch.object(norm_service, '_save_mappings', new_callable=AsyncMock):
            results = await norm_service.normalize_expenses_async(raw, document_id="test", total_units=50)

        assert len(results) == 1
        assert results[0].mapped_category == ExpenseCategory.CAPITAL_RESERVES

    @pytest.mark.asyncio
    async def test_no_units_does_not_crash(self, norm_service):
        """When total_units is 0 or unknown, insurance check gracefully skips per-unit logic."""
        raw = [{"description": "Building Insurance", "amount": 30000}]

        async def mock_map(batch, categories):
            return [{
                "original_text": "Building Insurance",
                "mapped_category": ExpenseCategory.INSURANCE.value,
                "confidence": 0.90,
                "reasoning": "Insurance",
            }]

        norm_service.llm_service.map_expenses_to_categories_async = mock_map
        with patch.object(norm_service, '_get_cached_mappings', new_callable=AsyncMock, return_value={}), \
             patch.object(norm_service, '_save_mappings', new_callable=AsyncMock):
            results = await norm_service.normalize_expenses_async(raw, document_id="test", total_units=0)

        assert len(results) == 1
        # No per-unit check possible, no limit/capex keywords → stays Insurance
        assert results[0].mapped_category == ExpenseCategory.INSURANCE


# ===========================================================================
# 1.4  OM Primacy — category-coverage rule
# ===========================================================================

class TestOMPrimacy:
    """
    Old behavior: OM with > 5 items discards all other sources.
    New behavior: OM must have >= 10 items AND cover 5 required categories
    (RE Tax, Insurance, Utilities, R&M, Management) to trigger primacy.
    """

    def test_sparse_om_keeps_t12(self, fin_service):
        """Sparse OM (6 items, missing categories) should NOT discard T12."""
        om_items = [
            _make_expense("Property Tax", 12000, ExpenseCategory.REAL_ESTATE_TAXES, "OM.pdf"),
            _make_expense("Insurance", 8000, ExpenseCategory.INSURANCE, "OM.pdf"),
            _make_expense("Management", 15000, ExpenseCategory.MANAGEMENT_FEES, "OM.pdf"),
            _make_expense("Legal", 3000, ExpenseCategory.GENERAL_ADMINISTRATIVE, "OM.pdf"),
            _make_expense("Marketing", 2000, ExpenseCategory.ADVERTISING_MARKETING, "OM.pdf"),
            _make_expense("Misc", 1000, ExpenseCategory.OTHER_OPERATING_EXPENSES, "OM.pdf"),
        ]
        t12_items = [
            _make_expense("Electric", 6000, ExpenseCategory.UTILITIES, "T12.pdf"),
            _make_expense("Plumbing Repair", 4000, ExpenseCategory.REPAIRS_MAINTENANCE, "T12.pdf"),
            _make_expense("Landscaping", 3000, ExpenseCategory.CONTRACT_SERVICES, "T12.pdf"),
        ]
        result = fin_service._deduplicate_expenses(om_items + t12_items)

        # T12 items should survive — OM is sparse (6 items, missing Utilities + R&M)
        descriptions = [e.original_text for e in result]
        assert "Electric" in descriptions, "T12 utilities should survive with sparse OM"
        assert "Plumbing Repair" in descriptions, "T12 R&M should survive with sparse OM"

    def test_complete_om_discards_t12(self, fin_service):
        """Complete OM (12 items, all 5 required categories) should discard T12."""
        om_items = [
            _make_expense("Property Tax", 12000, ExpenseCategory.REAL_ESTATE_TAXES, "Offering Memorandum.pdf"),
            _make_expense("Insurance", 8000, ExpenseCategory.INSURANCE, "Offering Memorandum.pdf"),
            _make_expense("Management Fee", 15000, ExpenseCategory.MANAGEMENT_FEES, "Offering Memorandum.pdf"),
            _make_expense("Water/Sewer", 6000, ExpenseCategory.UTILITIES, "Offering Memorandum.pdf"),
            _make_expense("General Repairs", 5000, ExpenseCategory.REPAIRS_MAINTENANCE, "Offering Memorandum.pdf"),
            _make_expense("Trash", 3000, ExpenseCategory.UTILITIES, "Offering Memorandum.pdf"),
            _make_expense("Landscaping", 4000, ExpenseCategory.CONTRACT_SERVICES, "Offering Memorandum.pdf"),
            _make_expense("Legal/Accounting", 3500, ExpenseCategory.GENERAL_ADMINISTRATIVE, "Offering Memorandum.pdf"),
            _make_expense("Marketing", 2000, ExpenseCategory.ADVERTISING_MARKETING, "Offering Memorandum.pdf"),
            _make_expense("Payroll", 20000, ExpenseCategory.PAYROLL, "Offering Memorandum.pdf"),
            _make_expense("Pest Control", 1200, ExpenseCategory.CONTRACT_SERVICES, "Offering Memorandum.pdf"),
            _make_expense("Reserves", 5000, ExpenseCategory.CAPITAL_RESERVES, "Offering Memorandum.pdf"),
        ]
        t12_items = [
            _make_expense("Electric Bill", 7200, ExpenseCategory.UTILITIES, "T12.pdf"),
            _make_expense("Plumber Invoice", 2500, ExpenseCategory.REPAIRS_MAINTENANCE, "T12.pdf"),
        ]
        result = fin_service._deduplicate_expenses(om_items + t12_items)

        descriptions = [e.original_text for e in result]
        assert "Electric Bill" not in descriptions, "T12 items should be discarded when OM is complete"
        assert "Plumber Invoice" not in descriptions
        # OM items should all survive
        assert "Property Tax" in descriptions
        assert "Water/Sewer" in descriptions

    def test_om_with_10_items_but_missing_categories_keeps_t12(self, fin_service):
        """OM has 10+ items but missing required categories → T12 survives."""
        # OM has 11 items but no Utilities or R&M
        om_items = [
            _make_expense("Tax 1", 5000, ExpenseCategory.REAL_ESTATE_TAXES, "OM.pdf"),
            _make_expense("Tax 2", 7000, ExpenseCategory.REAL_ESTATE_TAXES, "OM.pdf"),
            _make_expense("Insurance", 8000, ExpenseCategory.INSURANCE, "OM.pdf"),
            _make_expense("Mgmt", 15000, ExpenseCategory.MANAGEMENT_FEES, "OM.pdf"),
            _make_expense("Legal 1", 3000, ExpenseCategory.GENERAL_ADMINISTRATIVE, "OM.pdf"),
            _make_expense("Legal 2", 2000, ExpenseCategory.GENERAL_ADMINISTRATIVE, "OM.pdf"),
            _make_expense("Marketing 1", 1500, ExpenseCategory.ADVERTISING_MARKETING, "OM.pdf"),
            _make_expense("Marketing 2", 2500, ExpenseCategory.ADVERTISING_MARKETING, "OM.pdf"),
            _make_expense("Payroll 1", 10000, ExpenseCategory.PAYROLL, "OM.pdf"),
            _make_expense("Payroll 2", 12000, ExpenseCategory.PAYROLL, "OM.pdf"),
            _make_expense("Leasing", 3000, ExpenseCategory.LEASING_FEES, "OM.pdf"),
        ]
        t12_items = [
            _make_expense("Electric", 6000, ExpenseCategory.UTILITIES, "T12.pdf"),
            _make_expense("Plumbing", 4000, ExpenseCategory.REPAIRS_MAINTENANCE, "T12.pdf"),
        ]
        result = fin_service._deduplicate_expenses(om_items + t12_items)

        descriptions = [e.original_text for e in result]
        # Missing UTILITIES and REPAIRS_MAINTENANCE in OM → T12 should survive
        assert "Electric" in descriptions
        assert "Plumbing" in descriptions

    def test_verified_items_survive_om_primacy(self, fin_service):
        """User-verified items from non-OM sources survive even when OM triggers primacy."""
        om_items = [
            _make_expense("Tax", 12000, ExpenseCategory.REAL_ESTATE_TAXES, "Offering Memorandum.pdf"),
            _make_expense("Insurance", 8000, ExpenseCategory.INSURANCE, "Offering Memorandum.pdf"),
            _make_expense("Mgmt", 15000, ExpenseCategory.MANAGEMENT_FEES, "Offering Memorandum.pdf"),
            _make_expense("Water", 6000, ExpenseCategory.UTILITIES, "Offering Memorandum.pdf"),
            _make_expense("Repairs", 5000, ExpenseCategory.REPAIRS_MAINTENANCE, "Offering Memorandum.pdf"),
            _make_expense("Trash", 3000, ExpenseCategory.UTILITIES, "Offering Memorandum.pdf"),
            _make_expense("Landscape", 4000, ExpenseCategory.CONTRACT_SERVICES, "Offering Memorandum.pdf"),
            _make_expense("Legal", 3500, ExpenseCategory.GENERAL_ADMINISTRATIVE, "Offering Memorandum.pdf"),
            _make_expense("Marketing", 2000, ExpenseCategory.ADVERTISING_MARKETING, "Offering Memorandum.pdf"),
            _make_expense("Payroll", 20000, ExpenseCategory.PAYROLL, "Offering Memorandum.pdf"),
        ]
        verified_t12 = _make_expense(
            "Corrected Tax", 14000, ExpenseCategory.REAL_ESTATE_TAXES, "T12.pdf",
            user_verified=True,
        )
        result = fin_service._deduplicate_expenses(om_items + [verified_t12])

        descriptions = [e.original_text for e in result]
        assert "Corrected Tax" in descriptions, "User-verified item must survive OM primacy"
