from fastapi import APIRouter, Depends, HTTPException
from app.services.ingestion_service import IngestionService
from app.services.financial_service import FinancialService
from app.services.excel_service import ExcelService
from app.services.explainability_service import ExplainabilityService
from app.services.storage_service import storage_service
from app.services.progress_service import ProgressService
from app.models.schemas import UnderwritingAnalysis, DealParameters, DealPackage
from typing import Dict, Any
from app.dependencies import get_ingestion_service, get_financial_service, get_excel_service, get_explainability_service, get_progress_service
import logging
from datetime import datetime

logger = logging.getLogger(__name__)
router = APIRouter()

@router.post("/analysis/{document_id}", response_model=UnderwritingAnalysis)
async def perform_analysis(
    document_id: str,
    deal_parameters: DealParameters,
    ingestion_service: IngestionService = Depends(get_ingestion_service),
    financial_service: FinancialService = Depends(get_financial_service),
    excel_service: ExcelService = Depends(get_excel_service),
    explainability_service: ExplainabilityService = Depends(get_explainability_service),
    progress_service: ProgressService = Depends(get_progress_service),
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
    logger.info(f"Received deal parameters: {deal_parameters.model_dump_json(indent=2)}")
    
    await progress_service.update_progress(document_id, 10, "Starting analysis...")

    # ===== STEP 1: INGEST & NORMALIZE =====
    try:
        await progress_service.update_progress(document_id, 20, "Extracting and normalizing data from document...")
        analysis = await ingestion_service.ingest_pdf_document(document_id)
        logger.info(f"Ingestion complete. Property: {analysis.property_meta.address}, Units: {analysis.property_meta.total_units}")
        await progress_service.update_progress(document_id, 40, "Data extraction complete.")
    except Exception as e:
        logger.error(f"Ingestion failed: {str(e)}")
        await progress_service.update_progress(document_id, 0, f"Analysis failed: {str(e)}")
        raise HTTPException(status_code=400, detail=f"Ingestion failed: {str(e)}")

    # ===== STEP 2: CHECK DEAL VIABILITY (DETERMINISTIC) =====
    await progress_service.update_progress(document_id, 50, "Checking deal viability against criteria...")
    # Attach deal parameters to analysis
    analysis.deal_parameters = deal_parameters
    # Ensure the top-level exit_cap_rate is set from the start
    analysis.exit_cap_rate = deal_parameters.exit_cap_rate
    
    viability_check = financial_service.check_deal_viability(analysis)
    logger.info(f"Viability check: {viability_check['status']}")
    
    if viability_check["status"] == "FAIL":
        analysis.pass_fail_status = "FAIL"
        analysis.gating_reasons = viability_check["reasons"]
        logger.warning(f"Deal failed viability check: {viability_check['reasons']}")
        # Still return analysis object with FAIL status - frontend will display reasons
        await progress_service.update_progress(document_id, 100, "Analysis complete (Criteria Not Met).")
        return analysis
    
    # ===== STEP 3: CALCULATE FINANCIALS =====
    try:
        await progress_service.update_progress(document_id, 60, "Calculating historical performance (T12)...")
        # Calculate historical (from T12)
        historical_data = financial_service.calculate_historical(analysis)
        logger.info(f"Historical NOI: ${historical_data['historical_noi']:,.2f}")
        analysis.historical_noi = historical_data["historical_noi"]
        analysis.historical_cap_rate = historical_data["historical_cap_rate"]
        logger.info(f"AFTER historical calculation, analysis.exit_cap_rate: {getattr(analysis, 'exit_cap_rate', 'NOT SET')}")
        
        await progress_service.update_progress(document_id, 70, "Calculating pro forma projections...")
        # Calculate pro forma (with market rents & standard assumptions)
        pro_forma_data = financial_service.calculate_pro_forma(analysis)
        logger.info(f"pro_forma_data dictionary from financial_service: {pro_forma_data}")

        analysis.pro_forma_noi = pro_forma_data["pro_forma_noi"]
        analysis.pro_forma_expenses = pro_forma_data["pro_forma_expenses"]
        analysis.cap_rate = pro_forma_data["cap_rate"]
        analysis.exit_cap_rate = pro_forma_data.get("exit_cap_rate")
        logger.info(f"Pro Forma NOI: ${analysis.pro_forma_noi:,.2f}, Cap Rate: {analysis.cap_rate:.2%}")
        logger.info(f"AFTER pro_forma calculation, analysis.exit_cap_rate: {analysis.exit_cap_rate}")
    except Exception as e:
        logger.error(f"Financial calculation failed: {str(e)}")
        await progress_service.update_progress(document_id, 0, f"Calculation failed: {str(e)}")
        raise HTTPException(status_code=400, detail=f"Financial calculation failed: {str(e)}")
    
    # ===== STEP 3.5: GENERATE EXPLAINABILITY METADATA =====
    try:
        await progress_service.update_progress(document_id, 80, "Generating insights and explanations...")
        analysis = explainability_service.generate_explanations(analysis)
        logger.info("Explainability metadata generated successfully.")
    except Exception as e:
        logger.error(f"Explainability generation failed: {str(e)}")
        # We don't stop the pipeline, but we log it.
        analysis.gating_reasons.append(f"Explainability generation failed: {str(e)}")

    # ===== STEP 4: GENERATE OUTPUTS =====
    try:
        await progress_service.update_progress(document_id, 90, "Generating Excel model...")
        # Generate Excel model
        pro_forma_entries = excel_service.generate_side_by_side_view(analysis)
        excel_service.create_side_by_side_excel(pro_forma_entries)
        logger.info(f"Excel model generated for document: {document_id}")
    except Exception as e:
        logger.warning(f"Excel generation had issues (non-critical): {str(e)}")
        # Don't fail the whole analysis if Excel fails - it's a nice-to-have
    
    # ===== STEP 5: RETURN COMPLETE ANALYSIS =====
    await progress_service.update_progress(document_id, 100, "Analysis complete!")
    logger.info(f"Analysis complete. Final status: {analysis.pass_fail_status}")
    # FINAL CHECK: Ensure exit_cap_rate is correctly set and serialized
    analysis.exit_cap_rate = deal_parameters.exit_cap_rate
    
    logger.info(f"Analysis complete. Final status: {analysis.pass_fail_status}")
    logger.info(f"FINAL analysis object before return: {analysis.model_dump_json(indent=2)}")
    
    # ===== SAVE TO STORAGE =====
    # Save the analysis result so it can be retrieved later
    analysis_dict = analysis.model_dump()
    await storage_service.save_analysis_result(document_id, analysis_dict)

    # Also update/create a DealPackage entry for this single document analysis
    # This allows it to show up in the history list alongside multi-doc packages
    existing_package = await storage_service.get_deal_package(document_id)
    now = datetime.utcnow().isoformat()
    
    if existing_package:
        # Update existing
        package = DealPackage(**existing_package)
        package.updated_at = now
        package.normalization_status = "completed"
        # Ensure property name is set
        if not package.property_name or package.property_name == "Unknown":
            package.property_name = analysis.property_meta.address or f"Deal {document_id[:8]}"
    else:
        # Create new "wrapper" package for this single document
        package = DealPackage(
            package_id=document_id,
            property_name=analysis.property_meta.address or f"Deal {document_id[:8]}",
            created_at=now,
            updated_at=now,
            documents={}, # Single doc flow doesn't populate this yet, but that's fine
            normalization_status="completed",
            verification_progress=1.0
        )
    
    await storage_service.save_deal_package(package.model_dump())
    logger.info(f"Saved analysis and package wrapper for {document_id}")

    # Return a dictionary created from the model, ensuring correct field names
    return analysis