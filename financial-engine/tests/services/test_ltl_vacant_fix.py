"""
Regression tests for the Loss-to-Lease (LTL) vacant-unit fix.

Bug: Vacant units (current_rent=0) were counted in both LTL and vacancy loss,
inflating LTL by the vacant unit's full market rent and double-counting the loss.

Fix: LTL now subtracts the vacant rent gap (market - current per vacant unit)
so only occupied units' below-market gaps appear in LTL. Vacant unit income
loss is captured exclusively by the vacancy rate.

These tests verify the LTL formula: GPR - current_rent_annual - vacant_rent_gap_annual
"""

import pytest
from unittest.mock import MagicMock
from app.services.financial_service import FinancialService
from app.models.schemas import (
    UnderwritingAnalysis, DealParameters, PropertyMeta,
    RentRollSummary, RentRollItem
)
from app.services.audit_log_service import AuditLogService


@pytest.fixture
def service():
    return FinancialService(audit_log_service=MagicMock(spec=AuditLogService))


def _make_analysis(rent_roll_items, vacancy_rate=0.03):
    """Helper to build a minimal UnderwritingAnalysis with a rent roll."""
    items = []
    for u in rent_roll_items:
        items.append(RentRollItem(
            unit_number=str(u.get("unit", "1")),
            unit_type=u.get("unit_type", "1BR"),
            unit_size=u.get("unit_size", 500),
            tenant_name=u.get("tenant_name", "Tenant" if not u.get("is_vacant") else "Vacant"),
            current_rent=u["current_rent"],
            market_rent=u["market_rent"],
            is_vacant=u.get("is_vacant", False),
        ))

    total_units = len(items)
    occupied = sum(1 for i in items if not i.is_vacant)
    total_monthly = sum(i.current_rent or 0 for i in items)
    total_market = sum(i.market_rent or 0 for i in items)
    total_stabilized = sum(i.stabilized_rent or 0 for i in items)
    avg_size = sum(i.unit_size or 0 for i in items) / total_units if total_units else 0
    total_sf = sum(i.unit_size or 0 for i in items)

    return UnderwritingAnalysis(
        document_id="test_ltl",
        pass_fail_status="PASS",
        property_meta=PropertyMeta(
            purchase_price=1_000_000,
            total_units=total_units,
            year_built=2000,
            address="123 Test St",
        ),
        deal_parameters=DealParameters(vacancy_rate=vacancy_rate),
        rent_roll=items,
        rent_roll_summary=RentRollSummary(
            total_units=total_units,
            occupied_units=occupied,
            occupancy_rate=occupied / total_units if total_units else 0,
            avg_unit_size=avg_size,
            total_monthly_rent=total_monthly,
            total_annual_rent=total_monthly * 12,
            total_stabilized_rent=total_stabilized * 12,
            total_market_rent=total_market,
            avg_rent_per_unit=total_monthly / occupied if occupied else 0,
            avg_rent_per_sf=total_monthly / total_sf if total_sf else 0,
            avg_stabilized_per_unit=total_stabilized / total_units if total_units else 0,
            avg_stabilized_per_sf=total_stabilized / total_sf if total_sf else 0,
            avg_market_per_unit=total_market / total_units if total_units else 0,
            avg_market_per_sf=total_market / total_sf if total_sf else 0,
        ),
        historical_expenses=[],
    )


class TestLTLVacantFix:
    """LTL must exclude vacant units' rent gap to prevent double-counting."""

    def test_durant_avenue_real_deal(self, service):
        """2411 Durant Avenue — the deal that exposed the bug."""
        analysis = _make_analysis([
            {"unit": 1, "current_rent": 2795, "market_rent": 3500},
            {"unit": 2, "current_rent": 1935, "market_rent": 2400},
            {"unit": 3, "current_rent": 1895, "market_rent": 2400},
            {"unit": 4, "current_rent": 2752, "market_rent": 3500},
            {"unit": 5, "current_rent": 2895, "market_rent": 3500},
            {"unit": 6, "current_rent": 1995, "market_rent": 2400},
            {"unit": 7, "current_rent": 2895, "market_rent": 3500},
            {"unit": 8, "current_rent": 2695, "market_rent": 3500},
            {"unit": 9, "current_rent": 0, "market_rent": 2400, "is_vacant": True},
        ])
        service._calculate_revenue(analysis)

        assert analysis.gross_potential_rent == 325_200  # $27,100 * 12
        assert analysis.loss_to_lease == 58_116  # occupied gaps only, NOT $86,916
        assert analysis.vacancy_loss == 325_200 * 0.03  # $9,756

    def test_all_units_vacant(self, service):
        """All vacant → LTL=0, all loss captured by vacancy rate."""
        analysis = _make_analysis([
            {"unit": 1, "current_rent": 0, "market_rent": 2400, "is_vacant": True},
            {"unit": 2, "current_rent": 0, "market_rent": 3500, "is_vacant": True},
        ])
        service._calculate_revenue(analysis)

        assert analysis.loss_to_lease == 0

    def test_holdover_vacant_with_rent(self, service):
        """Vacant unit still paying rent (holdover) — only occupied gap in LTL."""
        analysis = _make_analysis([
            {"unit": 1, "current_rent": 2800, "market_rent": 3500},
            {"unit": 2, "current_rent": 1200, "market_rent": 2400, "is_vacant": True},
        ])
        service._calculate_revenue(analysis)

        # Only Unit 1 (occupied) gap: (3500-2800)*12 = $8,400
        assert analysis.loss_to_lease == 8_400

    def test_fully_occupied(self, service):
        """100% occupied — no vacant adjustment needed."""
        analysis = _make_analysis([
            {"unit": 1, "current_rent": 2800, "market_rent": 3500},
            {"unit": 2, "current_rent": 2100, "market_rent": 2400},
        ])
        service._calculate_revenue(analysis)

        expected = (3500 - 2800 + 2400 - 2100) * 12  # $12,000
        assert analysis.loss_to_lease == expected

    def test_at_market_with_vacant(self, service):
        """Occupied at market + vacant → LTL=0."""
        analysis = _make_analysis([
            {"unit": 1, "current_rent": 2400, "market_rent": 2400},
            {"unit": 2, "current_rent": 0, "market_rent": 2400, "is_vacant": True},
        ])
        service._calculate_revenue(analysis)

        assert analysis.loss_to_lease == 0

    def test_empty_rent_roll(self, service):
        """Empty rent roll → LTL=0."""
        analysis = _make_analysis([])
        service._calculate_revenue(analysis)

        assert analysis.loss_to_lease == 0
