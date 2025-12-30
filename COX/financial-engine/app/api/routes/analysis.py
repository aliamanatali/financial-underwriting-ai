from fastapi import APIRouter, Depends, HTTPException
from app.services.ingestion_service import IngestionService
from app.services.financial_service import FinancialService
from app.services.audit_log_service import AuditLogService
from app.models.schemas import UnderwritingAnalysis, DealParameters
from typing import Dict, Any
from app.dependencies import get_ingestion_service, get_financial_service, get_audit_log_service

router = APIRouter()

@router.post("/analysis/{document_id}", response_model=UnderwritingAnalysis)
async def perform_analysis(
    document_id: str,
    deal_parameters: DealParameters,
    ingestion_service: IngestionService = Depends(get_ingestion_service),
    financial_service: FinancialService = Depends(get_financial_service),
    audit_log_service: AuditLogService = Depends(get_audit_log_service),
):
    """
    Performs a full underwriting analysis on a given deal.
    
    Workflow:
    1. Ingest PDF from OCR backend
    2. Extract property meta, rent roll, expenses
    3. Normalize expenses to Valiance standard categories
    4. Check deal viability (gating logic)
    5. Calculate historical and pro forma financials
    6. Generate comprehensive audit trail
    7. Return complete UnderwritingAnalysis object
    """
    # 1. Ingest and process the document
    try:
        analysis = await ingestion_service.ingest_pdf_document(document_id)
        analysis.document_id = document_id
        analysis.pass_fail_status = "PASS"  # Default to PASS
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Document ingestion failed: {str(e)}")

    # 2. Check deal viability (gating checks)
    viability_check = financial_service.check_deal_viability({
        "unit_count": analysis.property_meta.total_units,
        "year_built": analysis.property_meta.year_built,
        "loan_amount": deal_parameters.loan_amount,
        "is_renovated": False  # Would need to be extracted from document
    })
    if viability_check["status"] == "FAIL":
        analysis.pass_fail_status = "FAIL"
        analysis.gating_reasons = viability_check["reasons"]
        analysis.audit_trail = audit_log_service.generate_audit_trail(analysis)
        return analysis
    
    # Mark as passed gating
    analysis.pass_fail_status = "PASS"
    analysis.gating_reasons = []

    # 3. Store deal parameters
    analysis.deal_parameters = deal_parameters

    # 4. Calculate Historical Financials (T12)
    try:
        historical_financials = financial_service.calculate_historical(analysis)
        analysis.historical_noi = historical_financials["historical_noi"]
        analysis.historical_cap_rate = historical_financials["historical_cap_rate"]
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Historical calculation failed: {str(e)}")

    # 5. Calculate Pro Forma Financials (F12) - Using Valiance 38% Expense Ratio Standard
    try:
        # Use the 38% expense ratio method (Valiance standard)
        pro_forma_data = financial_service.calculate_pro_forma_with_expense_ratio(
            analysis, 
            expense_ratio=0.38  # Valiance Capital standard
        )
        analysis.pro_forma_noi = pro_forma_data["pro_forma_noi"]
        analysis.cap_rate = pro_forma_data["cap_rate"]
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Pro forma calculation failed: {str(e)}")

    # 6. Generate comprehensive audit trail
    analysis.audit_trail = audit_log_service.generate_audit_trail(analysis)

    return analysis