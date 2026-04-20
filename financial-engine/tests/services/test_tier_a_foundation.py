"""
Tests for Tier A: Foundation changes.

A1: GeminiService removed
A2+A4: Deposit items → DEPOSIT category → excluded from OpEx
A3: Permit keyword narrowing
"""

import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from app.services.normalization_service import NormalizationService
from app.services.financial_service import FinancialService
from app.services.audit_log_service import AuditLogService
from app.models.schemas import (
    ExpenseCategory, StandardizedExpense, AuditLog,
    UnderwritingAnalysis, DealParameters, PropertyMeta,
    RentRollSummary,
)


@pytest.fixture
def norm_service():
    return NormalizationService(llm_service=MagicMock())


@pytest.fixture
def fin_service():
    return FinancialService(audit_log_service=MagicMock(spec=AuditLogService))


def _make_expense(text, amount, category, source_document=None):
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
    )


# ===========================================================================
# A1: GeminiService removed
# ===========================================================================

class TestGeminiServiceRemoved:

    def test_gemini_service_module_does_not_exist(self):
        """Importing the deleted module should raise ImportError."""
        with pytest.raises(ImportError):
            import importlib
            importlib.import_module("app.services.gemini_service")

    def test_gemini_client_still_importable(self):
        """GeminiClient is the surviving Gemini wrapper."""
        from app.services.gemini_client import GeminiClient
        assert GeminiClient is not None


# ===========================================================================
# A2 + A4: Deposit pair — classified as DEPOSIT, excluded from OpEx
# ===========================================================================

class TestDepositPair:

    @pytest.mark.asyncio
    async def test_security_deposit_classified_as_deposit(self, norm_service):
        """'Security Deposit' → forced to ExpenseCategory.DEPOSIT."""
        raw = [{"description": "Security Deposit", "amount": 1000}]

        async def mock_map(batch, categories):
            return [{
                "original_text": "Security Deposit",
                "mapped_category": ExpenseCategory.OTHER_OPERATING_EXPENSES.value,
                "confidence": 0.80,
                "reasoning": "Deposit",
            }]

        norm_service.llm_service.map_expenses_to_categories_async = mock_map
        with patch.object(norm_service, '_get_cached_mappings', new_callable=AsyncMock, return_value={}), \
             patch.object(norm_service, '_save_mappings', new_callable=AsyncMock):
            results = await norm_service.normalize_expenses_async(raw, document_id="test")

        assert len(results) == 1
        assert results[0].mapped_category == ExpenseCategory.DEPOSIT

    @pytest.mark.asyncio
    async def test_tenant_deposit_classified_as_deposit(self, norm_service):
        """'Tenant Deposit Refund' → forced to DEPOSIT."""
        raw = [{"description": "Tenant Deposit Refund", "amount": 500}]

        async def mock_map(batch, categories):
            return [{
                "original_text": "Tenant Deposit Refund",
                "mapped_category": ExpenseCategory.UNCATEGORIZED.value,
                "confidence": 0.70,
                "reasoning": "Refund",
            }]

        norm_service.llm_service.map_expenses_to_categories_async = mock_map
        with patch.object(norm_service, '_get_cached_mappings', new_callable=AsyncMock, return_value={}), \
             patch.object(norm_service, '_save_mappings', new_callable=AsyncMock):
            results = await norm_service.normalize_expenses_async(raw, document_id="test")

        assert len(results) == 1
        assert results[0].mapped_category == ExpenseCategory.DEPOSIT

    def test_deposit_excluded_from_opex(self, fin_service):
        """DEPOSIT items must NOT count toward T12 OpEx sum."""
        expenses = [
            _make_expense("Property Tax", 50000, ExpenseCategory.REAL_ESTATE_TAXES),
            _make_expense("Security Deposit", 1000, ExpenseCategory.DEPOSIT),
            _make_expense("Earnest Money Deposit", 50000, ExpenseCategory.DEPOSIT),
            _make_expense("Utilities", 10000, ExpenseCategory.UTILITIES),
        ]

        analysis = UnderwritingAnalysis(
            document_id="test_deposit",
            pass_fail_status="PASS",
            property_meta=PropertyMeta(purchase_price=1_000_000, total_units=10),
            deal_parameters=DealParameters(),
            rent_roll=[],
            rent_roll_summary=RentRollSummary(
                total_units=10, occupied_units=10, occupancy_rate=1.0,
                avg_unit_size=500, total_monthly_rent=0, total_annual_rent=0,
                total_stabilized_rent=0, total_market_rent=0,
                avg_rent_per_unit=0, avg_rent_per_sf=0,
                avg_stabilized_per_unit=0, avg_stabilized_per_sf=0,
                avg_market_per_unit=0, avg_market_per_sf=0,
            ),
            historical_expenses=expenses,
        )

        historical = fin_service.calculate_historical(analysis)

        # OpEx should be Tax + Utilities = $60,000
        # Deposits ($51,000) must NOT be included
        # The actual historical_expenses list should have deposits filtered out
        surviving_cats = [
            e.mapped_category for e in analysis.historical_expenses
        ]
        assert ExpenseCategory.DEPOSIT not in surviving_cats
        # NOI check: with zero rent, NOI = 0 - OpEx. Deposits excluded.
        assert historical["historical_noi"] == -(50000 + 10000)


# ===========================================================================
# A3: Permit keyword narrowing
# ===========================================================================

class TestPermitNarrowing:

    @pytest.mark.asyncio
    async def test_bare_permit_not_forced_to_capex(self, norm_service):
        """'Building Permit' alone → NOT forced to CapReserves."""
        raw = [{"description": "Building Permit", "amount": 200}]

        async def mock_map(batch, categories):
            return [{
                "original_text": "Building Permit",
                "mapped_category": ExpenseCategory.GENERAL_ADMINISTRATIVE.value,
                "confidence": 0.85,
                "reasoning": "Administrative expense",
            }]

        norm_service.llm_service.map_expenses_to_categories_async = mock_map
        with patch.object(norm_service, '_get_cached_mappings', new_callable=AsyncMock, return_value={}), \
             patch.object(norm_service, '_save_mappings', new_callable=AsyncMock):
            results = await norm_service.normalize_expenses_async(raw, document_id="test")

        assert len(results) == 1
        assert results[0].mapped_category == ExpenseCategory.GENERAL_ADMINISTRATIVE

    @pytest.mark.asyncio
    async def test_permit_for_renovation_forced_to_capex(self, norm_service):
        """'Building Permit for Renovation' → forced to CapReserves."""
        raw = [{"description": "Building Permit for Renovation", "amount": 1500}]

        async def mock_map(batch, categories):
            return [{
                "original_text": "Building Permit for Renovation",
                "mapped_category": ExpenseCategory.GENERAL_ADMINISTRATIVE.value,
                "confidence": 0.80,
                "reasoning": "Permit fee",
            }]

        norm_service.llm_service.map_expenses_to_categories_async = mock_map
        with patch.object(norm_service, '_get_cached_mappings', new_callable=AsyncMock, return_value={}), \
             patch.object(norm_service, '_save_mappings', new_callable=AsyncMock):
            results = await norm_service.normalize_expenses_async(raw, document_id="test")

        assert len(results) == 1
        assert results[0].mapped_category == ExpenseCategory.CAPITAL_RESERVES

    @pytest.mark.asyncio
    async def test_permit_for_new_construction_forced_to_capex(self, norm_service):
        """'Plumbing Permit for New Construction' → forced to CapReserves."""
        raw = [{"description": "Plumbing Permit for New Construction", "amount": 800}]

        async def mock_map(batch, categories):
            return [{
                "original_text": "Plumbing Permit for New Construction",
                "mapped_category": ExpenseCategory.REPAIRS_MAINTENANCE.value,
                "confidence": 0.75,
                "reasoning": "Plumbing work",
            }]

        norm_service.llm_service.map_expenses_to_categories_async = mock_map
        with patch.object(norm_service, '_get_cached_mappings', new_callable=AsyncMock, return_value={}), \
             patch.object(norm_service, '_save_mappings', new_callable=AsyncMock):
            results = await norm_service.normalize_expenses_async(raw, document_id="test")

        assert len(results) == 1
        assert results[0].mapped_category == ExpenseCategory.CAPITAL_RESERVES


# ===========================================================================
# Roof repair narrowing
# ===========================================================================

class TestRoofRepairNarrowing:

    @pytest.mark.asyncio
    async def test_minor_roof_repair_patching_not_capex(self, norm_service):
        """'Minor Roof Repair - Patching only' → NOT forced to CapReserves."""
        raw = [{"description": "Minor Roof Repair - Patching only", "amount": 0}]

        async def mock_map(batch, categories):
            return [{
                "original_text": "Minor Roof Repair - Patching only",
                "mapped_category": ExpenseCategory.REPAIRS_MAINTENANCE.value,
                "confidence": 0.85,
                "reasoning": "Roof maintenance",
            }]

        norm_service.llm_service.map_expenses_to_categories_async = mock_map
        with patch.object(norm_service, '_get_cached_mappings', new_callable=AsyncMock, return_value={}), \
             patch.object(norm_service, '_save_mappings', new_callable=AsyncMock):
            results = await norm_service.normalize_expenses_async(raw, document_id="test")

        assert len(results) == 1
        assert results[0].mapped_category == ExpenseCategory.REPAIRS_MAINTENANCE

    @pytest.mark.asyncio
    async def test_full_roof_replacement_is_capex(self, norm_service):
        """'Full Roof Replacement' → forced to CapReserves (via 'roof replacement' keyword)."""
        raw = [{"description": "Full Roof Replacement", "amount": 65000}]

        async def mock_map(batch, categories):
            return [{
                "original_text": "Full Roof Replacement",
                "mapped_category": ExpenseCategory.REPAIRS_MAINTENANCE.value,
                "confidence": 0.80,
                "reasoning": "Roof work",
            }]

        norm_service.llm_service.map_expenses_to_categories_async = mock_map
        with patch.object(norm_service, '_get_cached_mappings', new_callable=AsyncMock, return_value={}), \
             patch.object(norm_service, '_save_mappings', new_callable=AsyncMock):
            results = await norm_service.normalize_expenses_async(raw, document_id="test")

        assert len(results) == 1
        assert results[0].mapped_category == ExpenseCategory.CAPITAL_RESERVES

    @pytest.mark.asyncio
    async def test_roof_leak_patch_not_capex(self, norm_service):
        """'Roof leak patch' → NOT forced to CapReserves (maintenance qualifier)."""
        raw = [{"description": "Roof leak patch", "amount": 800}]

        async def mock_map(batch, categories):
            return [{
                "original_text": "Roof leak patch",
                "mapped_category": ExpenseCategory.REPAIRS_MAINTENANCE.value,
                "confidence": 0.90,
                "reasoning": "Leak repair",
            }]

        norm_service.llm_service.map_expenses_to_categories_async = mock_map
        with patch.object(norm_service, '_get_cached_mappings', new_callable=AsyncMock, return_value={}), \
             patch.object(norm_service, '_save_mappings', new_callable=AsyncMock):
            results = await norm_service.normalize_expenses_async(raw, document_id="test")

        assert len(results) == 1
        assert results[0].mapped_category == ExpenseCategory.REPAIRS_MAINTENANCE

    @pytest.mark.asyncio
    async def test_complete_roof_rebuild_is_capex(self, norm_service):
        """'Complete roof rebuild' → forced to CapReserves (via 'roof rebuild' keyword)."""
        raw = [{"description": "Complete roof rebuild", "amount": 80000}]

        async def mock_map(batch, categories):
            return [{
                "original_text": "Complete roof rebuild",
                "mapped_category": ExpenseCategory.REPAIRS_MAINTENANCE.value,
                "confidence": 0.75,
                "reasoning": "Roof work",
            }]

        norm_service.llm_service.map_expenses_to_categories_async = mock_map
        with patch.object(norm_service, '_get_cached_mappings', new_callable=AsyncMock, return_value={}), \
             patch.object(norm_service, '_save_mappings', new_callable=AsyncMock):
            results = await norm_service.normalize_expenses_async(raw, document_id="test")

        assert len(results) == 1
        assert results[0].mapped_category == ExpenseCategory.CAPITAL_RESERVES

    @pytest.mark.asyncio
    async def test_roof_repair_without_qualifier_is_capex(self, norm_service):
        """'Roof repair and waterproofing' with no maintenance qualifier → CapReserves."""
        raw = [{"description": "Roof repair and waterproofing", "amount": 22500}]

        async def mock_map(batch, categories):
            return [{
                "original_text": "Roof repair and waterproofing",
                "mapped_category": ExpenseCategory.REPAIRS_MAINTENANCE.value,
                "confidence": 0.80,
                "reasoning": "Roof work",
            }]

        norm_service.llm_service.map_expenses_to_categories_async = mock_map
        with patch.object(norm_service, '_get_cached_mappings', new_callable=AsyncMock, return_value={}), \
             patch.object(norm_service, '_save_mappings', new_callable=AsyncMock):
            results = await norm_service.normalize_expenses_async(raw, document_id="test")

        assert len(results) == 1
        assert results[0].mapped_category == ExpenseCategory.CAPITAL_RESERVES
