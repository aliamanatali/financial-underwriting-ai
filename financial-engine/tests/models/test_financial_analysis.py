import pytest
from pydantic import ValidationError
from app.models.financial_analysis import (
    ExpenseCategory,
    StandardizedExpense,
    RentRollSummary,
    DealParameters,
    UnderwritingAnalysis
)

def test_expense_category_enum():
    """Tests the ExpenseCategory enum."""
    assert ExpenseCategory.TAXES == "Property Taxes"
    assert ExpenseCategory.UTILITIES == "Utilities"

def test_standardized_expense_model():
    """Tests the StandardizedExpense model."""
    expense_data = {
        "original_text": "PG&E Bill",
        "mapped_category": ExpenseCategory.UTILITIES,
        "amount": 1200.50,
        "confidence": 0.98
    }
    expense = StandardizedExpense(**expense_data)
    assert expense.original_text == "PG&E Bill"
    assert expense.mapped_category == ExpenseCategory.UTILITIES

def test_rent_roll_summary_model():
    """Tests the RentRollSummary model."""
    summary_data = {
        "total_units": 50,
        "occupancy_%": 95.0,
        "average_rent_per_unit_type": {
            "Studio": 1500,
            "1BR": 2000
        }
    }
    summary = RentRollSummary(**summary_data)
    assert summary.total_units == 50
    assert summary.occupancy_percentage == 95.0

def test_deal_parameters_model():
    """Tests the DealParameters model with default values."""
    params = DealParameters()
    assert params.rent_growth == 0.03
    assert params.vacancy_rate == 0.03
    assert params.expense_ratio == 0.38

def test_underwriting_analysis_model():
    """Tests the UnderwritingAnalysis model."""
    analysis_data = {
        "document_id": "doc123",
        "pass_fail_status": "PASS",
        "normalized_expenses": [],
        "rent_roll_summary": {
            "total_units": 30,
            "occupancy_%": 92.0,
            "average_rent_per_unit_type": {"2BR": 2500}
        },
        "pro_forma_noi": 500000.0,
        "cap_rate": 0.05
    }
    analysis = UnderwritingAnalysis(**analysis_data)
    assert analysis.document_id == "doc123"
    assert analysis.pro_forma_noi == 500000.0

def test_rent_roll_summary_alias():
    """Tests that the 'occupancy_%' alias works correctly."""
    summary_data = {
        "total_units": 100,
        "occupancy_%": 97.0,
        "average_rent_per_unit_type": {}
    }
    summary = RentRollSummary.parse_obj(summary_data)
    assert summary.occupancy_percentage == 97.0