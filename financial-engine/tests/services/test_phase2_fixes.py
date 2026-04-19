"""
Phase 2 tests: rent roll and ingestion correctness.

Fix 1 — Vacancy helper: centralized is_unit_vacant() with move-in-date awareness.
Fix 2 — OM scenario selection: OM_SCENARIO_PREFERENCE constant, explicit logging.
"""

import logging
import pytest
from datetime import date
from unittest.mock import MagicMock

from app.models.schemas import (
    is_unit_vacant, RentRollItem,
    OMProformaTable, OMProformaRow,
)
from app.services.multi_document_extraction_service import (
    MultiDocumentExtractionService,
    OM_SCENARIO_PREFERENCE,
)


# ===========================================================================
# Fix 1 — Vacancy helper
# ===========================================================================

class TestIsUnitVacant:
    """Centralized vacancy detection via is_unit_vacant()."""

    def test_named_tenant_zero_rent_future_move_in(self):
        """Named tenant, $0 rent, future move-in → vacant."""
        assert is_unit_vacant(
            current_rent=0.0,
            tenant_name="Jane Doe",
            move_in_date="2027-01-15",
            analysis_date=date(2026, 4, 19),
        ) is True

    def test_named_tenant_zero_rent_past_move_in(self):
        """Named tenant, $0 rent, past move-in → NOT vacant (concession/gap)."""
        assert is_unit_vacant(
            current_rent=0.0,
            tenant_name="Jane Doe",
            move_in_date="2025-06-01",
            analysis_date=date(2026, 4, 19),
        ) is False

    def test_named_tenant_zero_rent_null_move_in(self):
        """Named tenant, $0 rent, null move-in → vacant (no active lease)."""
        assert is_unit_vacant(
            current_rent=0.0,
            tenant_name="Jane Doe",
            move_in_date=None,
        ) is True

    def test_named_tenant_zero_rent_tbd_move_in(self):
        """Named tenant, $0 rent, 'TBD' move-in → vacant (unparseable date)."""
        assert is_unit_vacant(
            current_rent=0.0,
            tenant_name="Jane Doe",
            move_in_date="TBD",
        ) is True

    def test_named_tenant_positive_rent_future_move_in(self):
        """Named tenant, positive rent, future move-in → NOT vacant."""
        assert is_unit_vacant(
            current_rent=1500.0,
            tenant_name="Jane Doe",
            move_in_date="2027-01-15",
            analysis_date=date(2026, 4, 19),
        ) is False

    def test_empty_tenant_zero_rent(self):
        """Empty tenant name, $0 rent → vacant (existing behavior)."""
        assert is_unit_vacant(current_rent=0.0, tenant_name="") is True

    def test_unknown_tenant_zero_rent(self):
        """'Unknown' tenant, $0 rent → vacant."""
        assert is_unit_vacant(current_rent=0.0, tenant_name="Unknown") is True

    def test_vacant_keyword_in_tenant(self):
        """'Vacant' in tenant name, $0 rent → vacant."""
        assert is_unit_vacant(current_rent=0.0, tenant_name="Vacant") is True

    def test_vacant_keyword_in_unit_type(self):
        """Vacancy keyword in unit_type → vacant regardless of rent."""
        assert is_unit_vacant(
            current_rent=0.0,
            tenant_name="Jane Doe",
            unit_type="Vacant Unit",
        ) is True

    def test_is_vacant_flag_already_true(self):
        """If is_vacant_flag is True, return True immediately."""
        assert is_unit_vacant(
            current_rent=1500.0,
            tenant_name="Jane Doe",
            is_vacant_flag=True,
        ) is True

    def test_positive_rent_no_keywords(self):
        """Normal occupied unit → NOT vacant."""
        assert is_unit_vacant(
            current_rent=2000.0,
            tenant_name="John Smith",
        ) is False

    def test_analysis_date_defaults_to_today(self):
        """When analysis_date is None, today is used as reference."""
        # A move-in date far in the future should be vacant regardless of today's date
        assert is_unit_vacant(
            current_rent=0.0,
            tenant_name="Jane Doe",
            move_in_date="2099-01-01",
            analysis_date=None,
        ) is True

    def test_pending_move_in_string(self):
        """'pending' is unparseable → treated as null → vacant."""
        assert is_unit_vacant(
            current_rent=0.0,
            tenant_name="Jane Doe",
            move_in_date="pending",
        ) is True

    def test_slash_date_format(self):
        """m/d/Y format is parseable."""
        # Past date with $0 rent = concession, NOT vacant
        assert is_unit_vacant(
            current_rent=0.0,
            tenant_name="Jane Doe",
            move_in_date="6/1/2025",
            analysis_date=date(2026, 4, 19),
        ) is False


class TestRentRollItemVacancyValidator:
    """Pydantic validator on RentRollItem delegates to is_unit_vacant."""

    def test_zero_rent_unknown_tenant_is_vacant(self):
        item = RentRollItem(unit_number="1", current_rent=0.0, tenant_name="Unknown")
        assert item.is_vacant is True

    def test_positive_rent_is_not_vacant(self):
        item = RentRollItem(unit_number="1", current_rent=1500.0, tenant_name="John")
        assert item.is_vacant is False

    def test_zero_rent_named_tenant_future_move_in(self):
        item = RentRollItem(
            unit_number="8",
            current_rent=0.0,
            tenant_name="Future Tenant",
            move_in_date="2099-01-01",
        )
        assert item.is_vacant is True

    def test_zero_rent_named_tenant_past_move_in(self):
        item = RentRollItem(
            unit_number="8",
            current_rent=0.0,
            tenant_name="Current Tenant",
            move_in_date="2020-01-01",
        )
        assert item.is_vacant is False

    def test_keystone_unit8_shape(self):
        """Keystone-shaped unit: named tenant, $0 rent, Aug 2025 move-in."""
        item = RentRollItem(
            unit_number="8",
            current_rent=0.0,
            tenant_name="New Tenant",
            market_rent=2400.0,
            move_in_date="2025-08-01",
        )
        # Aug 2025 is in the past relative to Apr 2026 → NOT vacant
        assert item.is_vacant is False

    def test_keystone_unit8_future(self):
        """If the same unit had a truly future move-in → vacant."""
        item = RentRollItem(
            unit_number="8",
            current_rent=0.0,
            tenant_name="New Tenant",
            market_rent=2400.0,
            move_in_date="2027-08-01",
        )
        assert item.is_vacant is True


class TestVacancyConsistencyAcrossCallSites:
    """All vacancy-setting call sites use is_unit_vacant."""

    def test_financial_service_uses_helper(self):
        """financial_service.py uses is_unit_vacant, not inline logic."""
        import inspect
        from app.services.financial_service import FinancialService
        source = inspect.getsource(FinancialService._calculate_revenue)
        assert "is_unit_vacant" in source, (
            "_calculate_revenue should use is_unit_vacant helper"
        )

    def test_normalization_service_uses_helper(self):
        """normalization_service.py uses is_unit_vacant, not inline logic."""
        import inspect
        from app.services.normalization_service import NormalizationService
        source = inspect.getsource(NormalizationService.normalize_rent_roll)
        assert "is_unit_vacant" in source, (
            "normalize_rent_roll should use is_unit_vacant helper"
        )

    def test_pydantic_validator_uses_helper(self):
        """RentRollItem.validate_vacancy_consistency uses is_unit_vacant."""
        import inspect
        source = inspect.getsource(RentRollItem.validate_vacancy_consistency)
        assert "is_unit_vacant" in source, (
            "validate_vacancy_consistency should delegate to is_unit_vacant"
        )


# ===========================================================================
# Fix 2 — OM scenario selection
# ===========================================================================

class TestOMScenarioSelection:
    """OM_SCENARIO_PREFERENCE constant is used for scenario selection."""

    @pytest.fixture
    def extraction_service(self):
        return MultiDocumentExtractionService(gemini_service=MagicMock())

    def test_constant_exists(self):
        assert isinstance(OM_SCENARIO_PREFERENCE, list)
        assert len(OM_SCENARIO_PREFERENCE) > 0

    def test_multi_scenario_stabilized_selected(self, extraction_service):
        """Multi-scenario OM with 'Stabilized' → Stabilized selected."""
        tables = [
            OMProformaTable(
                scenario_name="Proforma at Stabilized Rent",
                rows=[OMProformaRow(row_name="Insurance", annual=10000.0)],
            ),
            OMProformaTable(
                scenario_name="Proforma at Market Rents",
                rows=[OMProformaRow(row_name="Insurance", annual=12000.0)],
            ),
        ]
        result = extraction_service._convert_om_proforma_to_expenses(
            tables, "test.pdf", "doc-1"
        )
        # Stabilized has Insurance=10000
        assert len(result) == 1
        assert result[0]["amount"] == 10000.0

    def test_multi_scenario_stabilized_absent_warns(self, extraction_service, caplog):
        """Multi-scenario OM without preferred → first selected, WARNING logged."""
        tables = [
            OMProformaTable(
                scenario_name="Custom Scenario A",
                rows=[OMProformaRow(row_name="Insurance", annual=8000.0)],
            ),
            OMProformaTable(
                scenario_name="Custom Scenario B",
                rows=[OMProformaRow(row_name="Insurance", annual=9000.0)],
            ),
        ]
        with caplog.at_level(logging.WARNING):
            result = extraction_service._convert_om_proforma_to_expenses(
                tables, "test.pdf", "doc-1"
            )
        assert len(result) == 1
        assert result[0]["amount"] == 8000.0  # First table
        assert any("Falling back" in msg for msg in caplog.messages), (
            "Should log a WARNING when preferred scenario is not found"
        )

    def test_single_scenario_no_multi_log(self, extraction_service, caplog):
        """Single-scenario OM → no multi-scenario INFO log."""
        tables = [
            OMProformaTable(
                scenario_name="Only Scenario",
                rows=[OMProformaRow(row_name="Insurance", annual=7000.0)],
            ),
        ]
        with caplog.at_level(logging.INFO):
            result = extraction_service._convert_om_proforma_to_expenses(
                tables, "test.pdf", "doc-1"
            )
        assert len(result) == 1
        assert not any("Discarded" in msg for msg in caplog.messages), (
            "Single-scenario should not log discarded scenarios"
        )

    def test_tier1_current_takes_priority(self, extraction_service):
        """'Current' scenario beats OM_SCENARIO_PREFERENCE."""
        tables = [
            OMProformaTable(
                scenario_name="Proforma at Stabilized Rent",
                rows=[OMProformaRow(row_name="Insurance", annual=10000.0)],
            ),
            OMProformaTable(
                scenario_name="Current",
                rows=[OMProformaRow(row_name="Insurance", annual=15000.0)],
            ),
        ]
        result = extraction_service._convert_om_proforma_to_expenses(
            tables, "test.pdf", "doc-1"
        )
        assert result[0]["amount"] == 15000.0  # Current wins

    def test_multi_scenario_logs_discarded(self, extraction_service, caplog):
        """Multi-scenario with match → INFO log naming discarded scenarios."""
        tables = [
            OMProformaTable(
                scenario_name="Proforma at Stabilized Rent",
                rows=[OMProformaRow(row_name="Insurance", annual=10000.0)],
            ),
            OMProformaTable(
                scenario_name="Proforma at Market Rents",
                rows=[OMProformaRow(row_name="Insurance", annual=12000.0)],
            ),
        ]
        with caplog.at_level(logging.INFO):
            extraction_service._convert_om_proforma_to_expenses(
                tables, "test.pdf", "doc-1"
            )
        assert any("Discarded" in msg for msg in caplog.messages), (
            "Multi-scenario should log which scenarios were discarded"
        )

    def test_constant_used_not_hardcoded(self):
        """The selection logic references OM_SCENARIO_PREFERENCE, not hardcoded strings."""
        import inspect
        source = inspect.getsource(
            MultiDocumentExtractionService._convert_om_proforma_to_expenses
        )
        assert "OM_SCENARIO_PREFERENCE" in source, (
            "Scenario selection should use the OM_SCENARIO_PREFERENCE constant"
        )
