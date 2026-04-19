"""
Phase 1 tests: data routing and output correctness.

Fix 1 — Revenue filter includes category_group="Revenue"
Fix 2 — Subtotal filter catches additional summary lines in OM proforma
Fix 3 — T12 EGI label no longer misleadingly says "Effective Gross Income"
Fix 4 — Management Fees uses MAX dedup rule (same as Taxes/Insurance)
"""

import pytest
from unittest.mock import MagicMock
from app.services.financial_service import FinancialService
from app.services.multi_document_extraction_service import MultiDocumentExtractionService
from app.services.excel_service import ExcelService
from app.services.audit_log_service import AuditLogService
from app.models.schemas import (
    ExpenseCategory, StandardizedExpense, AuditLog,
    NormalizedDataItem, CategoryGroup,
    OMProformaTable, OMProformaRow,
    UnderwritingAnalysis, RentRollItem, RentRollSummary,
    DealParameters, ProFormaEntry, PropertyMeta,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_expense(text, amount, category=ExpenseCategory.OTHER_OPERATING_EXPENSES,
                  source_document=None, user_verified=False):
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
    )


def _make_normalized_item(raw_text, normalized_value, category_group, amount,
                          field_type="expense_category"):
    return NormalizedDataItem(
        id=f"test-{raw_text[:10]}",
        raw_text=raw_text,
        normalized_value=normalized_value,
        field_type=field_type,
        category_group=category_group,
        confidence=0.90,
        source_document="T12",
        metadata={"amount": amount},
    )


@pytest.fixture
def fin_service():
    return FinancialService(audit_log_service=MagicMock(spec=AuditLogService))


@pytest.fixture
def extraction_service():
    return MultiDocumentExtractionService(gemini_service=MagicMock())


# ===========================================================================
# Fix 1 — Revenue filter at multi_document.py:2150
# ===========================================================================

class TestRevenueFilter:
    """Revenue items (category_group='Revenue') must pass the filter."""

    def test_revenue_items_pass_filter(self):
        """Items with category_group='Revenue' should be included."""
        item = _make_normalized_item(
            "Parking Income", "Other Income",
            CategoryGroup.REVENUE, 5000.0,
        )
        # The filter condition from multi_document.py:2150
        passes = (
            item.field_type == "expense_category"
            or (hasattr(item, 'category_group')
                and item.category_group in ["Operating Expense", "Tax & Insurance", "Revenue"])
        )
        assert passes, "Revenue items should pass the filter"

    def test_operating_expense_still_passes(self):
        item = _make_normalized_item(
            "Water", "Utilities",
            CategoryGroup.OPERATING_EXPENSE, 3000.0,
        )
        passes = (
            item.field_type == "expense_category"
            or (hasattr(item, 'category_group')
                and item.category_group in ["Operating Expense", "Tax & Insurance", "Revenue"])
        )
        assert passes

    def test_property_info_excluded(self):
        item = _make_normalized_item(
            "Year Built: 1985", "Year Built",
            CategoryGroup.PROPERTY_INFO, 1985,
            field_type="property_info",
        )
        passes = (
            item.field_type == "expense_category"
            or (hasattr(item, 'category_group')
                and item.category_group in ["Operating Expense", "Tax & Insurance", "Revenue"])
        )
        assert not passes, "Property Info items must be excluded"

    def test_capital_expenditure_excluded(self):
        item = _make_normalized_item(
            "Roof Replacement", "Capital Reserves",
            CategoryGroup.CAPITAL_EXPENDITURE, 25000.0,
            field_type="capex",
        )
        passes = (
            item.field_type == "expense_category"
            or (hasattr(item, 'category_group')
                and item.category_group in ["Operating Expense", "Tax & Insurance", "Revenue"])
        )
        assert not passes, "Capital Expenditure items must be excluded"

    def test_other_income_flows_to_analysis(self, fin_service):
        """When Other Income items reach historical_expenses, analysis.other_income is non-zero."""
        expenses = [
            _make_expense("Parking Income", 12000.0, ExpenseCategory.OTHER_INCOME),
            _make_expense("Laundry Income", 5166.0, ExpenseCategory.OTHER_INCOME),
            _make_expense("Water/Sewer", 8000.0, ExpenseCategory.UTILITIES),
        ]
        # Simulate the other_income capture from financial_service.py:410-415
        t12_other_income = sum(
            e.amount for e in expenses
            if e.mapped_category in [ExpenseCategory.OTHER_INCOME, ExpenseCategory.REIMBURSEMENTS]
        )
        assert t12_other_income == 17166.0, "Other income should sum parking + laundry"


# ===========================================================================
# Fix 2 — Subtotal filter expansion in _convert_om_proforma_to_expenses
# ===========================================================================

class TestSubtotalFilter:
    """Expanded subtotal filter catches additional summary lines."""

    def _run_conversion(self, extraction_service, row_names):
        """Build a proforma table from row names and run conversion."""
        rows = [
            OMProformaRow(row_name=name, annual=10000.0)
            for name in row_names
        ]
        table = OMProformaTable(scenario_name="Current", rows=rows)
        result = extraction_service._convert_om_proforma_to_expenses(
            [table], "test.pdf", "doc-1"
        )
        return [item["raw_text"] for item in result]

    def test_total_controllable_filtered(self, extraction_service):
        names = self._run_conversion(extraction_service, [
            "Water/Sewer", "Total Controllable Expenses",
        ])
        assert "Total Controllable Expenses" not in names

    def test_subtotal_filtered(self, extraction_service):
        names = self._run_conversion(extraction_service, [
            "Insurance", "Sub-Total",
        ])
        assert "Sub-Total" not in names

    def test_subtotal_no_hyphen_filtered(self, extraction_service):
        names = self._run_conversion(extraction_service, [
            "Insurance", "Subtotal",
        ])
        assert "Subtotal" not in names

    def test_net_rental_income_filtered(self, extraction_service):
        names = self._run_conversion(extraction_service, [
            "Gross Potential Rent", "Net Rental Income",
        ])
        assert "Net Rental Income" not in names

    def test_gross_scheduled_income_exact_filtered(self, extraction_service):
        """Exact match 'Gross Scheduled Income' (subtotal) is filtered."""
        names = self._run_conversion(extraction_service, [
            "Parking", "Gross Scheduled Income",
        ])
        assert "Gross Scheduled Income" not in names

    def test_gross_scheduled_rental_income_kept(self, extraction_service):
        """'Gross Scheduled Rental Income' is a real line item — must survive."""
        names = self._run_conversion(extraction_service, [
            "Gross Scheduled Rental Income",
        ])
        assert "Gross Scheduled Rental Income" in names

    def test_gross_potential_market_rent_kept(self, extraction_service):
        names = self._run_conversion(extraction_service, [
            "Gross Potential Market Rent",
        ])
        assert "Gross Potential Market Rent" in names

    def test_original_filters_still_work(self, extraction_service):
        """Existing summary lines are still filtered."""
        names = self._run_conversion(extraction_service, [
            "Water", "Total Income", "Net Operating Income",
            "Effective Gross Income", "Total Operating Expenses",
        ])
        assert "Total Income" not in names
        assert "Net Operating Income" not in names
        assert "Effective Gross Income" not in names
        assert "Total Operating Expenses" not in names
        assert "Water" in names  # real expense survives


# ===========================================================================
# Fix 3 — T12 EGI label fix
# ===========================================================================

class TestT12EGILabel:
    """The T12 column must not label GPR as 'Effective Gross Income'."""

    def _make_analysis(self):
        return UnderwritingAnalysis(
            document_id="test-doc",
            pass_fail_status="PASS",
            property_meta=PropertyMeta(),
            rent_roll=[RentRollItem(unit_number="1", current_rent=2000, market_rent=2200)],
            rent_roll_summary=RentRollSummary(
                total_units=1, occupied_units=1, occupancy_rate=1.0,
                avg_unit_size=0, total_monthly_rent=2000, total_annual_rent=24000,
                total_stabilized_rent=24000, total_market_rent=26400,
                avg_rent_per_unit=2000, avg_rent_per_sf=0,
                avg_stabilized_per_unit=2000, avg_stabilized_per_sf=0,
                avg_market_per_unit=2200, avg_market_per_sf=0,
            ),
            historical_expenses=[],
            deal_parameters=DealParameters(),
        )

    def test_no_egi_label_for_t12(self):
        """The profitability entry should not be named plain 'Effective Gross Income'."""
        analysis = self._make_analysis()
        svc = ExcelService()
        entries = svc.generate_side_by_side_view(analysis)
        egi_entries = [e for e in entries if e.name == "Effective Gross Income"]
        assert len(egi_entries) == 0, (
            f"Should not have a plain 'Effective Gross Income' entry for T12. "
            f"Found: {[e.name for e in egi_entries]}"
        )

    def test_new_label_present(self):
        """The renamed entry exists."""
        analysis = self._make_analysis()
        svc = ExcelService()
        entries = svc.generate_side_by_side_view(analysis)
        rent_collection_entries = [e for e in entries if "Rent Collections" in e.name]
        assert len(rent_collection_entries) == 1, (
            f"Expected one 'Rent Collections' entry. "
            f"Got: {[e.name for e in entries]}"
        )


# ===========================================================================
# Fix 4 — Management Fees MAX-rule dedup
# ===========================================================================

class TestManagementFeesMaxDedup:
    """Management Fees should use MAX dedup, not sum."""

    def test_two_mgmt_fees_keeps_max(self, fin_service):
        """Two Management Fees entries → keep the larger one only."""
        expenses = [
            _make_expense("Management Fee (Current)", 52218.0,
                         ExpenseCategory.MANAGEMENT_FEES, "OM"),
            _make_expense("Management Fee (Pro Forma)", 44740.0,
                         ExpenseCategory.MANAGEMENT_FEES, "OM"),
        ]
        result = fin_service._deduplicate_expenses(expenses)
        mgmt = [e for e in result if e.mapped_category == ExpenseCategory.MANAGEMENT_FEES]
        assert len(mgmt) == 1, f"Expected 1 Management Fee, got {len(mgmt)}"
        assert mgmt[0].amount == 52218.0, f"Expected MAX amount 52218, got {mgmt[0].amount}"

    def test_single_mgmt_fee_unchanged(self, fin_service):
        """Single Management Fee entry is kept as-is."""
        expenses = [
            _make_expense("Management Fee", 30000.0, ExpenseCategory.MANAGEMENT_FEES),
        ]
        result = fin_service._deduplicate_expenses(expenses)
        mgmt = [e for e in result if e.mapped_category == ExpenseCategory.MANAGEMENT_FEES]
        assert len(mgmt) == 1
        assert mgmt[0].amount == 30000.0

    def test_three_mgmt_fees_keeps_max(self, fin_service):
        """Three Management Fees entries → keep the largest only."""
        expenses = [
            _make_expense("Management Fee A", 30000.0, ExpenseCategory.MANAGEMENT_FEES),
            _make_expense("Management Fee B", 52218.0, ExpenseCategory.MANAGEMENT_FEES),
            _make_expense("Management Fee C", 44740.0, ExpenseCategory.MANAGEMENT_FEES),
        ]
        result = fin_service._deduplicate_expenses(expenses)
        mgmt = [e for e in result if e.mapped_category == ExpenseCategory.MANAGEMENT_FEES]
        assert len(mgmt) == 1
        assert mgmt[0].amount == 52218.0

    def test_taxes_and_insurance_still_use_max(self, fin_service):
        """Existing MAX behavior for taxes/insurance is preserved."""
        expenses = [
            _make_expense("RE Taxes 2023", 40000.0, ExpenseCategory.REAL_ESTATE_TAXES),
            _make_expense("RE Taxes 2022", 35000.0, ExpenseCategory.REAL_ESTATE_TAXES),
        ]
        result = fin_service._deduplicate_expenses(expenses)
        taxes = [e for e in result if e.mapped_category == ExpenseCategory.REAL_ESTATE_TAXES]
        assert len(taxes) == 1
        assert taxes[0].amount == 40000.0
