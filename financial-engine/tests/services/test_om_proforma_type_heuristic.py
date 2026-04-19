"""
Tests for the OM proforma type heuristic in _convert_om_proforma_to_expenses.

Verifies that each row name is assigned the correct type/subtype before
the adapter maps it to section_context.
"""

import pytest
from unittest.mock import MagicMock
from app.services.multi_document_extraction_service import MultiDocumentExtractionService
from app.models.schemas import OMProformaTable, OMProformaRow


@pytest.fixture
def extraction_service():
    return MultiDocumentExtractionService(gemini_service=MagicMock())


def _make_proforma(rows_data):
    """Build a single-scenario proforma from (name, annual) tuples."""
    rows = [OMProformaRow(row_name=name, annual=annual) for name, annual in rows_data]
    return [OMProformaTable(scenario_name="Test", rows=rows)]


class TestOMProformaTypeHeuristic:

    def test_garage_parking_is_revenue(self, extraction_service):
        tables = _make_proforma([("Garage / Parking", 10800)])
        result = extraction_service._convert_om_proforma_to_expenses(tables, "om.pdf", "doc1")
        assert len(result) == 1
        assert result[0]["type"] == "revenue"
        assert result[0]["subtype"] == "other_income"

    def test_laundry_income_is_revenue(self, extraction_service):
        tables = _make_proforma([("Laundry Income", 5766)])
        result = extraction_service._convert_om_proforma_to_expenses(tables, "om.pdf", "doc1")
        assert result[0]["type"] == "revenue"
        assert result[0]["subtype"] == "other_income"

    def test_storage_income_is_revenue(self, extraction_service):
        tables = _make_proforma([("Storage Income", 3600)])
        result = extraction_service._convert_om_proforma_to_expenses(tables, "om.pdf", "doc1")
        assert result[0]["type"] == "revenue"
        assert result[0]["subtype"] == "other_income"

    def test_rent_control_is_expense(self, extraction_service):
        """'Rent Control / Other City Fees' must NOT be classified as revenue."""
        tables = _make_proforma([("Rent Control / Other City Fees", 12928)])
        result = extraction_service._convert_om_proforma_to_expenses(tables, "om.pdf", "doc1")
        assert result[0]["type"] == "expense"
        assert result[0]["subtype"] is None

    def test_rent_stabilization_is_expense(self, extraction_service):
        tables = _make_proforma([("Rent Stabilization Fees", 5000)])
        result = extraction_service._convert_om_proforma_to_expenses(tables, "om.pdf", "doc1")
        assert result[0]["type"] == "expense"

    def test_bare_rent_is_revenue(self, extraction_service):
        tables = _make_proforma([("Rent", 2400)])
        result = extraction_service._convert_om_proforma_to_expenses(tables, "om.pdf", "doc1")
        assert result[0]["type"] == "revenue"
        assert result[0]["subtype"] == "rent"

    def test_rental_income_is_revenue(self, extraction_service):
        tables = _make_proforma([("Rental Income", 120000)])
        result = extraction_service._convert_om_proforma_to_expenses(tables, "om.pdf", "doc1")
        assert result[0]["type"] == "revenue"
        # "rent" in "rental income" → subtype could be "rent" or "other_income"
        # "income" matches first in the keyword order → subtype = "other_income"
        # This is acceptable — both are revenue categories

    def test_business_other_taxes_is_expense(self, extraction_service):
        tables = _make_proforma([("Business / Other Taxes", 25770)])
        result = extraction_service._convert_om_proforma_to_expenses(tables, "om.pdf", "doc1")
        assert result[0]["type"] == "expense"

    def test_capital_reserves_is_capex(self, extraction_service):
        tables = _make_proforma([("Capital Reserves", 6400)])
        result = extraction_service._convert_om_proforma_to_expenses(tables, "om.pdf", "doc1")
        assert result[0]["type"] == "capex"

    def test_vending_is_revenue(self, extraction_service):
        tables = _make_proforma([("Vending Machine Revenue", 1200)])
        result = extraction_service._convert_om_proforma_to_expenses(tables, "om.pdf", "doc1")
        assert result[0]["type"] == "revenue"
        assert result[0]["subtype"] == "other_income"

    def test_pet_rent_is_revenue(self, extraction_service):
        tables = _make_proforma([("Pet Rent", 3600)])
        result = extraction_service._convert_om_proforma_to_expenses(tables, "om.pdf", "doc1")
        assert result[0]["type"] == "revenue"
        assert result[0]["subtype"] == "other_income"

    def test_reimbursement_is_revenue(self, extraction_service):
        tables = _make_proforma([("Utility Reimbursement", 8000)])
        result = extraction_service._convert_om_proforma_to_expenses(tables, "om.pdf", "doc1")
        assert result[0]["type"] == "revenue"
        assert result[0]["subtype"] == "reimbursement"

    def test_summary_lines_skipped(self, extraction_service):
        """NOI, Total Income, etc. should be skipped."""
        tables = _make_proforma([
            ("Property Tax", 50000),
            ("Net Operating Income", 200000),
            ("Total Expenses", 150000),
        ])
        result = extraction_service._convert_om_proforma_to_expenses(tables, "om.pdf", "doc1")
        assert len(result) == 1
        assert result[0]["raw_text"] == "Property Tax"
