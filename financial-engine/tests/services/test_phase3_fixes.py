"""
Phase 3 tests: underwriting assumption accuracy.

Fix 1 — Lease-up model for high-vacancy acquisitions.
Fix 2 — Default management fee injection when extraction returns $0.
Fix 3 — Business/Other Taxes classified as G&A, not Real Estate Taxes.
"""

import pytest
from unittest.mock import MagicMock
from app.services.financial_service import FinancialService
from app.services.audit_log_service import AuditLogService
from app.models.schemas import (
    ExpenseCategory, StandardizedExpense, AuditLog,
    UnderwritingAnalysis, RentRollItem, RentRollSummary,
    DealParameters, PropertyMeta, ProFormaExpenseItem,
)


# ── Helpers ───────────────────────────────────────────────────────────────

def _make_expense(text, amount, category, user_verified=False):
    return StandardizedExpense(
        original_text=text,
        mapped_category=category,
        amount=amount,
        confidence=0.90,
        audit_log=AuditLog(field_name="test", extracted_value=amount, source="T12", method="test"),
        user_verified=user_verified,
    )


def _make_analysis(n_units=32, n_vacant=8, market_rent=2800.0, current_rent=2000.0,
                   expenses=None, params=None):
    """Build a test analysis with n_units, n_vacant of them at $0 rent."""
    rent_roll = []
    for i in range(n_units):
        if i < n_vacant:
            rent_roll.append(RentRollItem(
                unit_number=str(i + 1), current_rent=0.0, market_rent=market_rent,
                tenant_name="Unknown", is_vacant=True,
            ))
        else:
            rent_roll.append(RentRollItem(
                unit_number=str(i + 1), current_rent=current_rent, market_rent=market_rent,
                tenant_name="Tenant", is_vacant=False,
            ))

    occupied = n_units - n_vacant
    total_monthly = occupied * current_rent
    total_annual = total_monthly * 12

    return UnderwritingAnalysis(
        document_id="test",
        pass_fail_status="PASS",
        property_meta=PropertyMeta(total_units=n_units, purchase_price=5_000_000),
        rent_roll=rent_roll,
        rent_roll_summary=RentRollSummary(
            total_units=n_units, occupied_units=occupied,
            occupancy_rate=occupied / n_units if n_units else 0,
            avg_unit_size=0, total_monthly_rent=total_monthly,
            total_annual_rent=total_annual,
            total_stabilized_rent=total_annual, total_market_rent=n_units * market_rent * 12,
            avg_rent_per_unit=current_rent, avg_rent_per_sf=0,
            avg_stabilized_per_unit=current_rent, avg_stabilized_per_sf=0,
            avg_market_per_unit=market_rent, avg_market_per_sf=0,
        ),
        historical_expenses=expenses or [],
        deal_parameters=params or DealParameters(),
    )


@pytest.fixture
def fin_service():
    return FinancialService(audit_log_service=MagicMock(spec=AuditLogService))


# ===========================================================================
# Fix 1 — Lease-up model
# ===========================================================================

class TestLeaseUpModel:

    def test_high_vacancy_triggers_leaseup(self, fin_service):
        """25% vacancy → lease-up loss applied."""
        analysis = _make_analysis(n_units=32, n_vacant=8, market_rent=3500.0)
        fin_service.calculate_pro_forma(analysis)
        assert analysis.year1_leaseup_loss is not None
        assert analysis.year1_leaseup_loss > 0
        # 8 units × $3,500 × 2 months = $56,000
        assert abs(analysis.year1_leaseup_loss - 56000.0) < 1.0

    def test_low_vacancy_no_leaseup(self, fin_service):
        """5% vacancy → no lease-up loss."""
        analysis = _make_analysis(n_units=20, n_vacant=1, market_rent=2500.0)
        fin_service.calculate_pro_forma(analysis)
        assert analysis.year1_leaseup_loss is None

    def test_exactly_10pct_no_leaseup(self, fin_service):
        """Exactly 10% vacancy → no lease-up loss (strict inequality)."""
        analysis = _make_analysis(n_units=10, n_vacant=1, market_rent=2500.0)
        fin_service.calculate_pro_forma(analysis)
        assert analysis.year1_leaseup_loss is None

    def test_above_10pct_triggers(self, fin_service):
        """11% vacancy → lease-up loss applied."""
        analysis = _make_analysis(n_units=9, n_vacant=1, market_rent=2400.0)
        fin_service.calculate_pro_forma(analysis)
        assert analysis.year1_leaseup_loss is not None
        # 1 unit × $2,400 × 2 months = $4,800
        assert abs(analysis.year1_leaseup_loss - 4800.0) < 1.0

    def test_year1_egi_less_than_stabilized(self, fin_service):
        """Year 1 EGI < stabilized EGI when lease-up triggers."""
        analysis = _make_analysis(n_units=32, n_vacant=8, market_rent=3500.0)
        fin_service.calculate_pro_forma(analysis)
        assert analysis.effective_gross_income < analysis.stabilized_egi

    def test_year1_noi_less_than_stabilized(self, fin_service):
        """Year 1 NOI < stabilized NOI when lease-up triggers."""
        analysis = _make_analysis(n_units=32, n_vacant=8, market_rent=3500.0)
        fin_service.calculate_pro_forma(analysis)
        assert analysis.pro_forma_noi < analysis.stabilized_noi

    def test_stabilized_noi_none_when_no_leaseup(self, fin_service):
        """No lease-up → stabilized_noi is None (no distinction needed)."""
        analysis = _make_analysis(n_units=20, n_vacant=1, market_rent=2500.0)
        fin_service.calculate_pro_forma(analysis)
        assert analysis.stabilized_noi is None


# ===========================================================================
# Fix 2 — Default management fee
# ===========================================================================

class TestDefaultMgmtFee:

    def test_extracted_mgmt_fee_uses_extracted(self, fin_service):
        """Deal with extracted mgmt fee → source = 'extracted'."""
        expenses = [
            _make_expense("Management Fee", 40000.0, ExpenseCategory.MANAGEMENT_FEES),
            _make_expense("Insurance", 10000.0, ExpenseCategory.INSURANCE),
        ]
        analysis = _make_analysis(expenses=expenses)
        fin_service.calculate_pro_forma(analysis)
        assert analysis.mgmt_fee_source == "extracted"

    def test_no_mgmt_fee_injects_default(self, fin_service):
        """Deal with no mgmt fee → injects default, source = 'default_injected'."""
        expenses = [
            _make_expense("Insurance", 10000.0, ExpenseCategory.INSURANCE),
        ]
        analysis = _make_analysis(expenses=expenses)
        fin_service.calculate_pro_forma(analysis)
        assert analysis.mgmt_fee_source == "default_injected"
        # Should be 4% of EGI
        mgmt_items = [e for e in analysis.pro_forma_expenses_detailed
                      if e.name == ExpenseCategory.MANAGEMENT_FEES.value]
        assert len(mgmt_items) == 1
        expected = (analysis.effective_gross_income or 0) * 0.04
        assert abs(mgmt_items[0].amount - expected) < 1.0

    def test_zero_mgmt_fee_treated_as_absent(self, fin_service):
        """$0 extracted mgmt fee → treated as absent, injects default."""
        expenses = [
            _make_expense("Management Fee", 0.0, ExpenseCategory.MANAGEMENT_FEES),
            _make_expense("Insurance", 10000.0, ExpenseCategory.INSURANCE),
        ]
        analysis = _make_analysis(expenses=expenses)
        fin_service.calculate_pro_forma(analysis)
        assert analysis.mgmt_fee_source == "default_injected"

    def test_user_verified_takes_priority(self, fin_service):
        """User-verified mgmt fee → source = 'user_override'."""
        expenses = [
            _make_expense("Management Fee", 50000.0, ExpenseCategory.MANAGEMENT_FEES,
                         user_verified=True),
        ]
        analysis = _make_analysis(expenses=expenses)
        fin_service.calculate_pro_forma(analysis)
        assert analysis.mgmt_fee_source == "user_override"


# ===========================================================================
# Fix 3 — Business/Other Taxes classification (fallback mapper)
# ===========================================================================

class TestBusinessTaxClassification:
    """Fallback keyword mapper distinguishes business taxes from property taxes."""

    @pytest.fixture
    def norm_service(self):
        from app.services.normalization_service import NormalizationService
        return NormalizationService(llm_service=MagicMock())

    def test_business_other_taxes_maps_to_ga(self, norm_service):
        items = [{"description": "Business / Other Taxes", "amount": 7000}]
        result = norm_service._fallback_simple_mapping_raw(items)
        assert result[0]["mapped_category"] == ExpenseCategory.GENERAL_ADMINISTRATIVE.value

    def test_ad_valorem_maps_to_re_taxes(self, norm_service):
        items = [{"description": "Ad Valorem Property Taxes", "amount": 30000}]
        result = norm_service._fallback_simple_mapping_raw(items)
        assert result[0]["mapped_category"] == ExpenseCategory.REAL_ESTATE_TAXES.value

    def test_city_business_license_maps_to_ga(self, norm_service):
        items = [{"description": "City Business License Tax", "amount": 2000}]
        result = norm_service._fallback_simple_mapping_raw(items)
        assert result[0]["mapped_category"] == ExpenseCategory.GENERAL_ADMINISTRATIVE.value

    def test_parcel_tax_maps_to_re_taxes(self, norm_service):
        items = [{"description": "Parcel Tax", "amount": 5000}]
        result = norm_service._fallback_simple_mapping_raw(items)
        assert result[0]["mapped_category"] == ExpenseCategory.REAL_ESTATE_TAXES.value

    def test_franchise_tax_maps_to_ga(self, norm_service):
        items = [{"description": "Franchise Tax", "amount": 3000}]
        result = norm_service._fallback_simple_mapping_raw(items)
        assert result[0]["mapped_category"] == ExpenseCategory.GENERAL_ADMINISTRATIVE.value
