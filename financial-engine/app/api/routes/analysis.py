from fastapi import APIRouter, Depends, HTTPException
from app.services.ingestion_service import IngestionService
from app.services.financial_service import FinancialService
from app.services.excel_service import ExcelService
from app.models.schemas import UnderwritingAnalysis, DealParameters
from typing import Dict, Any
from app.dependencies import get_ingestion_service, get_financial_service, get_excel_service
import logging

logger = logging.getLogger(__name__)
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
    
    Pipeline:
    1. Ingest & Normalize: Extract data from OCR, normalize categories
    2. Check Viability: Apply deterministic gating criteria
    3. Calculate Financials: Pro forma and historical metrics
    4. Generate Output: Excel model
    5. Return: Full analysis with audit trail
    """
    logger.info(f"Starting analysis for document: {document_id}")
    logger.info(f"Deal parameters: {deal_parameters.dict()}")
    
    # ===== STEP 1: INGEST & NORMALIZE =====
    try:
        analysis = await ingestion_service.ingest_pdf_document(document_id)
        logger.info(f"Ingestion complete. Property: {analysis.property_meta.address}, Units: {analysis.property_meta.total_units}")
    except Exception as e:
        logger.error(f"Ingestion failed: {str(e)}")
        raise HTTPException(status_code=400, detail=f"Ingestion failed: {str(e)}")

    # ===== STEP 2: CHECK DEAL VIABILITY (DETERMINISTIC) =====
    # Attach deal parameters to analysis
    analysis.deal_parameters = deal_parameters
    
    viability_check = financial_service.check_deal_viability(analysis)
    logger.info(f"Viability check: {viability_check['status']}")
    
    if viability_check["status"] == "FAIL":
        analysis.pass_fail_status = "FAIL"
        analysis.gating_reasons = viability_check["reasons"]
        logger.warning(f"Deal failed viability check: {viability_check['reasons']}")
        # Still return analysis object with FAIL status - frontend will display reasons
        return analysis
    
    # ===== STEP 3: CALCULATE FINANCIALS =====
    try:
        # Calculate historical (from T12)
        historical_data = financial_service.calculate_historical(analysis)
        logger.info(f"Historical NOI: ${historical_data['historical_noi']:,.2f}")
        analysis.historical_noi = historical_data["historical_noi"]
        analysis.historical_cap_rate = historical_data["historical_cap_rate"]
        
        # Calculate pro forma (with market rents & standard assumptions)
        pro_forma_data = financial_service.calculate_pro_forma(analysis)
        analysis.pro_forma_noi = pro_forma_data["pro_forma_noi"]
        analysis.pro_forma_expenses = pro_forma_data["pro_forma_expenses"]
        analysis.cap_rate = pro_forma_data["cap_rate"]
        logger.info(f"Pro Forma NOI: ${analysis.pro_forma_noi:,.2f}, Cap Rate: {analysis.cap_rate:.2%}")
    except Exception as e:
        logger.error(f"Financial calculation failed: {str(e)}")
        raise HTTPException(status_code=400, detail=f"Financial calculation failed: {str(e)}")
    
    # ===== STEP 4: GENERATE OUTPUTS =====
    try:
        # Generate Excel model
        excel_service.create_side_by_side_excel(analysis)
        logger.info(f"Excel model generated for document: {document_id}")
    except Exception as e:
        logger.warning(f"Excel generation had issues (non-critical): {str(e)}")
        # Don't fail the whole analysis if Excel fails - it's a nice-to-have
    
    # ===== STEP 5: RETURN COMPLETE ANALYSIS =====
    logger.info(f"Analysis complete. Final status: {analysis.pass_fail_status}")
    return analysis