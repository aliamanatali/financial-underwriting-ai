"""
Phase 2.5 tests: extraction determinism for OM documents.

When structured proforma extraction succeeds on an OM document, the generic
visual extraction path is skipped to prevent nondeterministic duplicates.
"""

import pytest
from unittest.mock import MagicMock, AsyncMock, patch

from app.models.schemas import (
    OMProformaTable, OMProformaRow, DocumentType,
)
from app.services.multi_document_extraction_service import MultiDocumentExtractionService


@pytest.fixture
def extraction_service():
    mock_gemini = MagicMock()
    svc = MultiDocumentExtractionService(gemini_service=mock_gemini)
    return svc


def _make_om_doc(filename="OM_Test.pdf"):
    return {
        "content": b"fake-pdf-bytes",
        "filename": filename,
        "document_category": DocumentType.OFFERING_MEMORANDUM.value,
        "document_id": "doc-om-1",
    }


def _make_financial_doc(filename="T12_Statement.pdf"):
    return {
        "content": b"fake-pdf-bytes",
        "filename": filename,
        "document_category": DocumentType.FINANCIALS.value,
        "document_id": "doc-fin-1",
    }


def _proforma_tables():
    """Minimal proforma table that passes the 'succeeded' check."""
    return [
        OMProformaTable(
            scenario_name="Proforma at Stabilized Rent",
            rows=[
                OMProformaRow(row_name="Insurance", annual=10000.0),
                OMProformaRow(row_name="Repairs and Maintenance", annual=5000.0),
            ],
        ),
    ]


class TestOMVisualExtractionSkip:
    """Visual extraction is skipped for OM docs when proforma succeeds."""

    @pytest.mark.asyncio
    async def test_om_with_proforma_skips_visual(self, extraction_service):
        """OM document with successful proforma → visual extraction NOT called."""
        doc = _make_om_doc()

        with patch.object(
            extraction_service, "extract_om_proforma_from_pdf",
            new_callable=AsyncMock, return_value=_proforma_tables(),
        ) as mock_proforma, patch.object(
            extraction_service.om_scraper_service, "extract_om_key_data",
            new_callable=AsyncMock, return_value={},
        ), patch.object(
            extraction_service, "extract_from_visual_document",
            new_callable=AsyncMock, return_value=[],
        ) as mock_visual:
            result = await extraction_service.process_financial_documents(
                [doc], task_id="test-pkg"
            )
            mock_proforma.assert_called_once()
            mock_visual.assert_not_called()

    @pytest.mark.asyncio
    async def test_om_with_failed_proforma_falls_back_to_visual(self, extraction_service):
        """OM document with failed proforma → visual extraction IS called."""
        doc = _make_om_doc()

        with patch.object(
            extraction_service, "extract_om_proforma_from_pdf",
            new_callable=AsyncMock, return_value=[],  # Empty = failed
        ) as mock_proforma, patch.object(
            extraction_service.om_scraper_service, "extract_om_key_data",
            new_callable=AsyncMock, return_value={},
        ), patch.object(
            extraction_service, "extract_from_visual_document",
            new_callable=AsyncMock, return_value=[{"raw_text": "Fallback item", "amount": 100}],
        ) as mock_visual:
            result = await extraction_service.process_financial_documents(
                [doc], task_id="test-pkg"
            )
            mock_proforma.assert_called_once()
            mock_visual.assert_called_once()

    @pytest.mark.asyncio
    async def test_non_om_always_runs_visual(self, extraction_service):
        """Non-OM document → visual extraction IS called (unchanged behavior)."""
        doc = _make_financial_doc()

        with patch.object(
            extraction_service, "extract_from_visual_document",
            new_callable=AsyncMock, return_value=[{"raw_text": "Water Bill", "amount": 200}],
        ) as mock_visual:
            result = await extraction_service.process_financial_documents(
                [doc], task_id="test-pkg"
            )
            mock_visual.assert_called_once()

    @pytest.mark.asyncio
    async def test_om_proforma_items_have_no_scenario_prefix(self, extraction_service):
        """Multi-scenario OM → only selected-scenario items, no prefixed duplicates."""
        tables = [
            OMProformaTable(
                scenario_name="Proforma at Stabilized Rent",
                rows=[
                    OMProformaRow(row_name="Insurance", annual=10000.0),
                    OMProformaRow(row_name="Repairs and Maintenance", annual=5000.0),
                ],
            ),
            OMProformaTable(
                scenario_name="Proforma at Market Rents",
                rows=[
                    OMProformaRow(row_name="Insurance", annual=12000.0),
                    OMProformaRow(row_name="Repairs and Maintenance", annual=6000.0),
                ],
            ),
        ]

        result = extraction_service._convert_om_proforma_to_expenses(
            tables, "test.pdf", "doc-1"
        )

        raw_texts = [item["raw_text"] for item in result]
        # No items should have "Proforma at" prefix — only clean row names
        prefixed = [t for t in raw_texts if t.startswith("Proforma at")]
        assert len(prefixed) == 0, f"Found scenario-prefixed items: {prefixed}"
        # Should have items from selected scenario only
        assert "Insurance" in raw_texts
        assert "Repairs and Maintenance" in raw_texts

    @pytest.mark.asyncio
    async def test_om_proforma_no_spurious_items(self, extraction_service):
        """Proforma extraction doesn't produce spurious items like 'Building Size'."""
        tables = [
            OMProformaTable(
                scenario_name="Proforma at Stabilized Rent",
                rows=[
                    OMProformaRow(row_name="Insurance", annual=10000.0),
                    OMProformaRow(row_name="Utilities", annual=8000.0),
                    OMProformaRow(row_name="Property Taxes", annual=20000.0),
                ],
            ),
        ]

        result = extraction_service._convert_om_proforma_to_expenses(
            tables, "test.pdf", "doc-1"
        )

        raw_texts = [item["raw_text"] for item in result]
        spurious = ["Building Size", "Lot Size", "Number of Units", "Parking"]
        for s in spurious:
            assert s not in raw_texts, f"Spurious item '{s}' found in proforma output"
