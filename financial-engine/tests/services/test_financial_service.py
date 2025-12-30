import pytest
from app.services.financial_service import FinancialService
from app.models.financial_analysis import (
    UnderwritingAnalysis,
    DealParameters,
    DealData,
    RentRollSummary,
    StandardizedExpense,
    ExpenseCategory,
)

@pytest.fixture
def financial_service():
    """Provides a FinancialService instance for testing."""
    return FinancialService()

def test_check_deal_viability_pass(financial_service):
    """
    Tests that a deal meeting all criteria passes the viability check.
    """
    deal_data = {
        "unit_count": 50,
        "loan_amount": 10_000_000,
        "year_built": 1985,
        "is_renovated": True
    }
    result = financial_service.check_deal_viability(deal_data)
    assert result["status"] == "PASS"
    assert not result["reasons"]

def test_check_deal_viability_fail_unit_count(financial_service):
    """
    Tests that a deal fails if the unit count is too low.
    """
    deal_data = {"unit_count": 10}
    result = financial_service.check_deal_viability(deal_data)
    assert result["status"] == "FAIL"
    assert any("Unit count" in s for s in result["reasons"])

def test_check_deal_viability_fail_loan_amount(financial_service):
    """
    Tests that a deal fails if the loan amount is too small.
    """
    deal_data = {
        "unit_count": 30,
        "loan_amount": 4_000_000
    }
    result = financial_service.check_deal_viability(deal_data)
    assert result["status"] == "FAIL"
    assert any("Loan amount" in s for s in result["reasons"])

def test_check_deal_viability_fail_year_built(financial_service):
    """
    Tests that a deal fails if it was built before 1970 and is not renovated.
    """
    deal_data = {
        "unit_count": 40,
        "loan_amount": 8_000_000,
        "year_built": 1965,
        "is_renovated": False
    }
    result = financial_service.check_deal_viability(deal_data)
    assert result["status"] == "FAIL"
    assert any("Property built" in s for s in result["reasons"])

def test_check_deal_viability_year_built_pass_if_renovated(financial_service):
    """
    Tests that a deal passes if it was built before 1970 but has been renovated.
    """
    deal_data = {
        "unit_count": 40,
        "loan_amount": 8_000_000,
        "year_built": 1965,
        "is_renovated": True
    }
    result = financial_service.check_deal_viability(deal_data)
    assert result["status"] == "PASS"

def test_calculate_pro_forma(financial_service):
    """
    Tests the Pro Forma calculation logic.
    """
    deal_data = DealData(
        purchase_price=10_000_000,
        closing_costs=200_000,
        holding_period_years=5,
        sell_cap_rate=0.05,
        historical_noi=500_000,
        rent_roll_summary=RentRollSummary(
            total_units=50,
            **{"occupancy_%": 0.95},
            average_rent_per_unit_type={"1BR": 1500, "2BR": 2000}
        ),
        normalized_expenses=[
            StandardizedExpense(original_text="Taxes", mapped_category=ExpenseCategory.TAXES, amount=150000, confidence=1.0),
            StandardizedExpense(original_text="Insurance", mapped_category=ExpenseCategory.INSURANCE, amount=50000, confidence=1.0),
        ],
        deal_parameters=DealParameters(vacancy_rate=0.05)
    )

    result = financial_service.calculate_pro_forma(deal_data)

    # Expected GPR = (1500 + 2000) * 12 = 42000
    # Expected Vacancy Loss = 42000 * 0.05 = 2100
    # Expected EGI = 42000 - 2100 = 39900
    # Expected Total Expenses = 150000 + 50000 = 200000
    # Expected Pro Forma NOI = 39900 - 200000 = -160100
    # Expected Cap Rate = -160100 / 10_000_000 = -0.01601
    assert result["pro_forma_noi"] == pytest.approx(-160100, 0.01)
    assert result["cap_rate"] == pytest.approx(-0.01601, 0.01)