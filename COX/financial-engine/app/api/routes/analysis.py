from fastapi import APIRouter, Depends, HTTPException
from app.services.ingestion_service import IngestionService
from app.services.financial_service import FinancialService
from app.services.excel_service import ExcelService
from app.models.schemas import UnderwritingAnalysis, DealParameters
from typing import Dict, Any
from app.dependencies import get_ingestion_service, get_financial_service, get_excel_service

router = APIRouter()

@router.post("/analysis/{document_id}", response_model=UnderwritingAnalysis)
async def perform_analysis(
    document_id: str,
    deal_parameters: DealParameters,
    ingestion_service: IngestionService = Depends(get_ingestion_service),
    financial_service: FinancialService = Depends(get_financial_service),
    excel_service: ExcelService = Depends(get_excel_service),
):
    """
    Performs a full underwriting analysis on a given deal.
    """
    # 1. Ingest and process the document
    try:
        analysis = ingestion_service.ingest_pdf_document(document_id)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

    # 2. Check deal viability
    viability_check = financial_service.check_deal_viability(analysis.property_meta.dict())
    if viability_check["status"] == "FAIL":
        analysis.pass_fail_status = "FAIL"
        analysis.gating_reasons = viability_check["reasons"]
        return analysis

    # 3. Calculate Pro Forma
    analysis.deal_parameters = deal_parameters
    pro_forma_data = financial_service.calculate_pro_forma(analysis)
    analysis.pro_forma_noi = pro_forma_data["pro_forma_noi"]
    analysis.cap_rate = pro_forma_data["cap_rate"]

    # 4. Generate Excel report and get audit trail
    excel_service.create_side_by_side_excel(analysis)
    analysis.audit_trail = financial_service.get_audit_trail()

    return analysis